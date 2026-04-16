-- 迁移：将 embedding 列从 vector(1024) 改为 vector(768)
-- 旧的 hash embedding 无语义价值，直接清空重建

ALTER TABLE rules DROP COLUMN IF EXISTS embedding;
ALTER TABLE rules ADD COLUMN embedding vector(768);

-- 迁移后需要重新生成所有 embedding:
-- POST /api/search/embed-all
