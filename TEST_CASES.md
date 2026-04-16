# PRD 知识库 API 测试用例

## 测试环境

- 后端: http://localhost:8000
- 数据库: PostgreSQL + pgvector
- LLM: MetaRouter (Claude API)

---

## 1. 健康检查 API

### 1.1 Ping 测试
```bash
curl -s http://localhost:8000/api/ping
```
**期望结果**: `{"status":"ok","service":"prd-knowledge-base"}`

### 1.2 规则统计
```bash
curl -s http://localhost:8000/api/rules/stats
```
**期望结果**:
```json
{
  "total": 38,
  "by_domain": {"结账分账": 24, ...},
  "by_status": {"draft": 37, "active": 1},
  "by_category": {"资金流转规则": 21, ...}
}
```

### 1.3 健康概览
```bash
curl -s http://localhost:8000/api/health/overview
```
**期望结果**:
```json
{
  "total_rules": 38,
  "active_rules": 1,
  "challenged_rules": 0,
  "deprecated_rules": 0,
  "open_challenges": 0,
  "total_hits": 0,
  "cold_rules": 1
}
```

---

## 2. PRD 管理 API

### 2.1 获取 PRD 列表
```bash
curl -s http://localhost:8000/api/prds/
```

### 2.2 上传 PRD 文件
```bash
curl -X POST -F "file=@/path/to/prd.docx" http://localhost:8000/api/prds/upload
```
**期望结果**: 返回 PRD 对象，status="uploaded"

### 2.3 解析 PRD
```bash
curl -X POST http://localhost:8000/api/prds/{id}/parse
```
**期望结果**: `{"status":"parsed","sections_count":11,"prd_id":2}`

### 2.4 删除 PRD
```bash
curl -X DELETE http://localhost:8000/api/prds/{id}
```

---

## 3. 规则管理 API

### 3.1 获取规则列表
```bash
# 基础列表
curl -s http://localhost:8000/api/rules/

# 按领域筛选 (中文需 URL 编码)
curl -s "http://localhost:8000/api/rules/?domain=%E7%BB%93%E8%B4%A6%E5%88%86%E8%B4%A6"

# 按状态筛选
curl -s "http://localhost:8000/api/rules/?status=draft"

# 文本搜索
curl -s "http://localhost:8000/api/rules/?q=退款"
```

### 3.2 获取规则详情
```bash
curl -s http://localhost:8000/api/rules/1
```

### 3.3 更新规则
```bash
curl -X PUT "http://localhost:8000/api/rules/1?actor=tester" \
  -H "Content-Type: application/json" \
  -d '{"status": "active"}'
```

### 3.4 创建质疑
```bash
curl -X POST http://localhost:8000/api/rules/1/challenges \
  -H "Content-Type: application/json" \
  -d '{"challenger":"张三","content":"这条规则和项目B冲突"}'
```

### 3.5 解决质疑
```bash
curl -X PUT "http://localhost:8000/api/rules/challenges/1/resolve?actor=李四" \
  -H "Content-Type: application/json" \
  -d '{"resolution":"已确认，修改了规则","status":"resolved"}'
```

---

## 4. 分析 API

### 4.1 LLM 提取规则
```bash
curl -X POST http://localhost:8000/api/analysis/extract/{prd_id}
```
**期望结果**: `{"status":"extracted","rules_count":10,"prd_id":2}`

### 4.2 规则对比
```bash
curl -s http://localhost:8000/api/analysis/compare
```
**期望结果**:
```json
{
  "conflicts": [...],
  "total_compared": 38,
  "categories_checked": 5
}
```

### 4.3 风险概览
```bash
curl -s http://localhost:8000/api/analysis/risks
```
**期望结果**:
```json
{
  "summary": {"total_rules": 38, "high_risk_count": 0, "avg_risk_score": 15.2},
  "high_risk_rules": [],
  "distribution": {"low": 30, "medium": 8, "high": 0}
}
```

---

## 5. 搜索 API

### 5.1 语义搜索
```bash
# 中文需 URL 编码
curl -s "http://localhost:8000/api/search/?q=%E9%80%80%E6%AC%BE&limit=5"
```

### 5.2 批量生成 Embedding
```bash
curl -X POST http://localhost:8000/api/search/embed-all
```

---

## 6. 审计与健康 API

### 6.1 审计日志
```bash
curl -s http://localhost:8000/api/rules/1/logs
```

### 6.2 热门规则
```bash
curl -s "http://localhost:8000/api/health/top-hits?limit=10"
```

### 6.3 冷门规则
```bash
curl -s "http://localhost:8000/api/health/cold-rules?limit=20"
```

### 6.4 最近活动
```bash
curl -s "http://localhost:8000/api/health/recent-activity?limit=20"
```

---

## 7. 完整流程测试

```bash
#!/bin/bash
# 完整流程测试脚本

BASE="http://localhost:8000"

# 1. 上传
echo "1. 上传 PRD..."
PRD_ID=$(curl -s -X POST -F "file=@test.docx" $BASE/api/prds/upload | jq .id)
echo "   PRD ID: $PRD_ID"

# 2. 解析
echo "2. 解析文档..."
curl -s -X POST $BASE/api/prds/$PRD_ID/parse

# 3. 提取规则
echo "3. LLM 提取规则..."
curl -s -X POST $BASE/api/analysis/extract/$PRD_ID

# 4. 查看提取的规则
echo "4. 查看规则..."
curl -s "$BASE/api/rules/?prd_id=$PRD_ID" | jq 'length'

# 5. 搜索测试
echo "5. 语义搜索..."
curl -s "$BASE/api/search/?q=退款&limit=3" | jq 'length'

# 6. 风险分析
echo "6. 风险分析..."
curl -s $BASE/api/analysis/risks | jq '.summary'

echo "完成!"
```

---

## 测试结果 (2026-04-14)

| 模块 | 测试用例数 | 通过 | 失败 |
|-----|-----------|------|------|
| 健康检查 | 4 | 4 | 0 |
| PRD 管理 | 4 | 4 | 0 |
| 规则管理 | 6 | 6 | 0 |
| 分析功能 | 3 | 3 | 0 |
| 搜索功能 | 2 | 2 | 0 |
| 审计健康 | 4 | 4 | 0 |
| **总计** | **23** | **23** | **0** |

**注意事项**:
- 中文参数需要 URL 编码
- 语义搜索需要配置 Voyage API Key
- LLM 提取需要配置 Anthropic API Key
