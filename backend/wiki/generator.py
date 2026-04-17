"""Wiki 输出层 - 借鉴 Karpathy LLM Wiki 的三层架构"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session
from models import Material, Rule, WikiPage, WikiLog

logger = logging.getLogger(__name__)

WIKI_DIR = "./wiki_output"


class WikiGenerator:
    """Wiki 生成器 - 维护持久化的结构化知识"""

    def __init__(self):
        os.makedirs(WIKI_DIR, exist_ok=True)

    async def generate_for_material(self, material: Material, rules: list[Rule], db: Session) -> dict:
        """为单个材料生成 Wiki 页面"""

        # 1. 生成规则摘要页面
        summary_page = self._generate_rule_summary_page(material, rules, db)

        # 2. 生成概念页面（按 category 分组）
        concept_pages = self._generate_concept_pages(material, rules, db)

        # 3. 更新 index.md
        self._update_index(material, summary_page, concept_pages)

        # 4. 追加 log.md
        self._append_log(material, "generate_wiki", {
            "pages_created": len(concept_pages) + 1,
            "rules_covered": len(rules)
        })

        # 5. 记录 WikiLog
        db.add(WikiLog(
            operation="generate_wiki",
            actor="system",
            target_type="material",
            target_id=material.id,
            details={"pages": len(concept_pages) + 1, "rules": len(rules)}
        ))
        db.commit()

        return {
            "summary_page_id": summary_page.id if summary_page else None,
            "concept_pages_count": len(concept_pages),
            "wiki_dir": WIKI_DIR
        }

    def _generate_rule_summary_page(self, material: Material, rules: list[Rule], db: Session) -> Optional[WikiPage]:
        """生成规则摘要页面"""
        if not rules:
            return None

        # 按章节分组
        sections = {}
        for rule in rules:
            section = rule.source_section or "未分类"
            if section not in sections:
                sections[section] = []
            sections[section].append(rule)

        # 构建 markdown 内容
        lines = [
            f"# {material.title} - 规则摘要",
            f"\n> 来源：{material.source_channel} | 类型：{material.doc_type}",
            f"\n## 概览",
            f"\n- 总规则数：{len(rules)}",
            f"- 章节数：{len(sections)}",
            f"- 处理耗时：{material.process_elapsed or 0}s",
            f"\n---\n"
        ]

        for section, section_rules in sections.items():
            lines.append(f"\n## {section}\n")
            for rule in section_rules:
                lines.append(f"- **[{rule.category or '未分类'}]** {rule.rule_text}")
                if rule.params:
                    params_str = json.dumps(rule.params, ensure_ascii=False)
                    lines.append(f"  - 参数：{params_str}")
                if rule.confidence and rule.confidence < 0.7:
                    lines.append(f"  - ⚠️ 置信度：{rule.confidence:.1%}")

        content = "\n".join(lines)
        page_path = f"{WIKI_DIR}/{material.id}_summary.md"

        # 写入文件
        with open(page_path, "w", encoding="utf-8") as f:
            f.write(content)

        # 创建 WikiPage 记录
        page = WikiPage(
            material_id=material.id,
            title=f"{material.title} - 规则摘要",
            page_type="rule_summary",
            page_path=page_path,
            markdown_content=content,
            related_rules=[r.id for r in rules],
            last_generated_at=datetime.now()
        )
        db.add(page)
        db.commit()
        db.refresh(page)

        return page

    def _generate_concept_pages(self, material: Material, rules: list[Rule], db: Session) -> list[WikiPage]:
        """按 category 生成概念页面"""
        by_category = {}
        for rule in rules:
            cat = rule.category or "未分类"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(rule)

        pages = []
        for category, cat_rules in by_category.items():
            lines = [
                f"# {category}",
                f"\n> 来自材料：{material.title}",
                f"\n## 规则列表 ({len(cat_rules)} 条)\n"
            ]

            for rule in cat_rules:
                lines.append(f"\n### 规则 {rule.id}\n")
                lines.append(f"{rule.rule_text}\n")
                if rule.structured_logic:
                    logic = rule.structured_logic
                    if "if" in logic:
                        lines.append(f"- **条件**：{logic['if']}")
                    if "then" in logic:
                        lines.append(f"- **动作**：{logic['then']}")
                    if "constraint" in logic:
                        lines.append(f"- **约束**：{logic['constraint']}")

            content = "\n".join(lines)
            safe_cat = category.replace("/", "_").replace(" ", "_")
            page_path = f"{WIKI_DIR}/{material.id}_{safe_cat}.md"

            with open(page_path, "w", encoding="utf-8") as f:
                f.write(content)

            page = WikiPage(
                material_id=material.id,
                title=category,
                page_type="concept",
                page_path=page_path,
                markdown_content=content,
                related_rules=[r.id for r in cat_rules],
                last_generated_at=datetime.now()
            )
            db.add(page)
            pages.append(page)

        db.commit()
        return pages

    def _update_index(self, material: Material, summary_page: Optional[WikiPage], concept_pages: list[WikiPage]):
        """更新 index.md"""
        index_path = f"{WIKI_DIR}/index.md"

        # 读取现有 index
        if os.path.exists(index_path):
            with open(index_path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "# 知识库索引\n\n> 基于 Karpathy LLM Wiki 架构，知识编译后持久化存储\n\n## 最近更新\n\n"

        # 构建新条目
        new_entry = f"- **[{material.title}](./{material.id}_summary.md)** - {len(concept_pages)} 个概念页面 - {datetime.now().strftime('%Y-%m-%d %H:%M')}\n"

        # 找到最近更新部分并插入
        if "## 最近更新" in content:
            parts = content.split("## 最近更新", 1)
            rest = parts[1].split("\n##", 1) if "\n##" in parts[1] else [parts[1], ""]
            content = parts[0] + "## 最近更新\n\n" + new_entry + rest[0] + ("\n##" + rest[1] if rest[1] else "")
        else:
            content += f"\n## 最近更新\n\n{new_entry}"

        with open(index_path, "w", encoding="utf-8") as f:
            f.write(content)

    def _append_log(self, material: Material, operation: str, details: dict):
        """追加 log.md"""
        log_path = f"{WIKI_DIR}/log.md"

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"| {timestamp} | {operation} | {material.title} | {json.dumps(details, ensure_ascii=False)} |\n"

        if not os.path.exists(log_path):
            header = "# Wiki 操作日志\n\n| 时间 | 操作 | 对象 | 详情 |\n|------|------|------|------|\n"
            entry = header + entry

        with open(log_path, "a", encoding="utf-8") as f:
            f.write(entry)

    async def update_for_new_material(self, new_material: Material, new_rules: list[Rule], db: Session):
        """增量更新：新材料加入后，更新已有 Wiki 页面"""

        # 1. 查找相似规则，更新交叉引用
        await self._update_cross_references(new_rules, db)

        # 2. 更新相关的概念页面
        await self._update_related_concept_pages(new_rules, db)

    async def _update_cross_references(self, new_rules: list[Rule], db: Session):
        """为新规则查找相似规则，建立交叉引用"""
        import numpy as np

        for rule in new_rules:
            if not rule.embedding:
                continue

            # 查找已有 Wiki 页面
            existing_pages = db.query(WikiPage).filter(
                WikiPage.related_rules.isnot(None)
            ).all()

            for page in existing_pages:
                # 计算相似度
                for existing_rule_id in page.related_rules or []:
                    existing_rule = db.query(Rule).filter(Rule.id == existing_rule_id).first()
                    if existing_rule and existing_rule.embedding:
                        new_emb = np.array(rule.embedding)
                        exist_emb = np.array(existing_rule.embedding)

                        # 余弦相似度
                        similarity = np.dot(new_emb, exist_emb) / (np.linalg.norm(new_emb) * np.linalg.norm(exist_emb))

                        if similarity > 0.85:
                            # 更新交叉引用
                            cross_refs = page.cross_references or {}
                            cross_refs[rule.id] = {
                                "relation": "similar",
                                "similarity": float(similarity)
                            }
                            page.cross_references = cross_refs
                            page.is_dirty = True
                            db.commit()

    async def _update_related_concept_pages(self, new_rules: list[Rule], db: Session):
        """更新与新规则相关的概念页面"""
        by_category = {}
        for rule in new_rules:
            cat = rule.category or "未分类"
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(rule)

        for category, rules in by_category.items():
            # 查找已有该 category 的 Wiki 页面
            existing = db.query(WikiPage).filter(
                WikiPage.page_type == "concept",
                WikiPage.title == category
            ).first()

            if existing:
                # 添加新规则到相关列表
                related = existing.related_rules or []
                related.extend([r.id for r in rules])
                existing.related_rules = related
                existing.is_dirty = True
                existing.version += 1
                db.commit()


# 全局实例
wiki_generator = WikiGenerator()