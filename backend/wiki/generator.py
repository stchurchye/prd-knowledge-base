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

        # 3. LLM 驱动的知识综合
        synthesis_page = await self._generate_llm_synthesis(material, rules, db)

        # 4. 检测与已有规则的矛盾
        contradiction_page = await self._detect_contradictions(material, rules, db)

        # 5. 更新 index.md
        self._update_index(material, summary_page, concept_pages)

        # 6. 追加 log.md
        self._append_log(material, "generate_wiki", {
            "pages_created": len(concept_pages) + 1 + (1 if synthesis_page else 0),
            "rules_covered": len(rules),
            "has_synthesis": synthesis_page is not None,
            "contradictions_found": contradiction_page is not None
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


    async def _generate_llm_synthesis(self, material: Material, rules: list[Rule], db: Session) -> Optional[WikiPage]:
        """LLM 驱动的知识综合 - 生成深度分析页面"""
        if not rules or len(rules) < 2:
            return None

        try:
            from extractors.llm_client import get_llm_client, get_model_name
            client = get_llm_client()
            model = get_model_name()
        except Exception:
            logger.warning("LLM 客户端不可用，跳过知识综合")
            return None

        rules_text = "\n".join(f"- [{r.category or '未分类'}] {r.rule_text}" for r in rules[:50])

        prompt = (
            f"你是知识库维护专家。以下是从材料「{material.title}」中提取的 {len(rules)} 条业务规则。\n\n"
            f"请生成一份知识综合报告，包含：\n"
            f"1. 核心发现：这些规则反映了什么业务逻辑和设计思路\n"
            f"2. 关键实体：涉及哪些角色、系统、流程\n"
            f"3. 规则间关系：哪些规则互相依赖、互相约束\n"
            f"4. 潜在风险：哪些规则可能存在歧义或遗漏\n"
            f"5. 建议：需要进一步确认或补充的内容\n\n"
            f"=== 规则列表 ===\n{rules_text}\n\n"
            f"请用 Markdown 格式输出。"
        )

        try:
            response = client.chat.completions.create(
                model=model, max_tokens=4096,
                messages=[{"role": "user", "content": prompt}],
            )
            content = response.choices[0].message.content

            page_path = f"{WIKI_DIR}/{material.id}_synthesis.md"
            with open(page_path, "w", encoding="utf-8") as f:
                f.write(content)

            page = WikiPage(
                material_id=material.id,
                title=f"{material.title} - 知识综合",
                page_type="synthesis",
                page_path=page_path,
                markdown_content=content,
                related_rules=[r.id for r in rules],
                last_generated_at=datetime.now()
            )
            db.add(page)
            db.commit()
            db.refresh(page)
            return page

        except Exception as e:
            logger.warning("知识综合生成失败: %s", e)
            return None

    async def _detect_contradictions(self, material: Material, rules: list[Rule], db: Session) -> Optional[WikiPage]:
        """检测新规则与已有规则的矛盾"""
        import numpy as np

        new_rules_with_emb = [r for r in rules if r.embedding is not None]
        if not new_rules_with_emb:
            return None

        existing_rules = db.query(Rule).filter(
            Rule.material_id != material.id,
            Rule.status != "deprecated",
            Rule.embedding.isnot(None)
        ).all()

        if not existing_rules:
            return None

        contradictions = []
        ex_embs = np.array([r.embedding for r in existing_rules])
        ex_norms = np.linalg.norm(ex_embs, axis=1, keepdims=True)
        ex_norms[ex_norms == 0] = 1
        ex_normalized = ex_embs / ex_norms

        opposites = [
            ("允许", "禁止"), ("可以", "不可以"), ("支持", "不支持"),
            ("必须", "不得"), ("需要", "不需要"), ("开启", "关闭"),
        ]

        for new_rule in new_rules_with_emb:
            new_emb = np.array(new_rule.embedding)
            new_norm = np.linalg.norm(new_emb)
            if new_norm == 0:
                continue
            sims = ex_normalized @ (new_emb / new_norm)

            for idx in np.where(sims > 0.8)[0]:
                existing = existing_rules[idx]
                t1 = (new_rule.rule_text or "").lower()
                t2 = (existing.rule_text or "").lower()

                for pos, neg in opposites:
                    if (pos in t1 and neg in t2) or (neg in t1 and pos in t2):
                        contradictions.append({
                            "new_rule_id": new_rule.id,
                            "new_rule_text": new_rule.rule_text[:100],
                            "existing_rule_id": existing.id,
                            "existing_rule_text": existing.rule_text[:100],
                            "similarity": float(sims[idx]),
                            "conflict_type": f"{pos}/{neg}"
                        })
                        break

        if not contradictions:
            return None

        lines = [
            f"# 矛盾检测报告 - {material.title}",
            f"\n> 检测时间：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"\n发现 **{len(contradictions)}** 处潜在矛盾：\n"
        ]
        for i, c in enumerate(contradictions, 1):
            lines.append(f"\n## 矛盾 {i} (相似度: {c['similarity']:.2f})")
            lines.append(f"\n**新规则** (ID: {c['new_rule_id']}): {c['new_rule_text']}")
            lines.append(f"\n**已有规则** (ID: {c['existing_rule_id']}): {c['existing_rule_text']}")
            lines.append(f"\n冲突类型: {c['conflict_type']}\n")

        content = "\n".join(lines)
        page_path = f"{WIKI_DIR}/{material.id}_contradictions.md"

        with open(page_path, "w", encoding="utf-8") as f:
            f.write(content)

        page = WikiPage(
            material_id=material.id,
            title=f"{material.title} - 矛盾检测",
            page_type="contradiction_report",
            page_path=page_path,
            markdown_content=content,
            last_generated_at=datetime.now()
        )
        db.add(page)
        db.commit()
        db.refresh(page)
        return page


# 全局实例
wiki_generator = WikiGenerator()