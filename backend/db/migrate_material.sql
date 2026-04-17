-- migrate_material.sql - 数据模型迁移脚本

-- 1. 创建 materials 表（从 prds 复制并扩展）
CREATE TABLE materials (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    filename VARCHAR(300) NOT NULL,
    file_hash VARCHAR(32) UNIQUE,
    material_type VARCHAR(30) DEFAULT 'document',
    doc_type VARCHAR(20) DEFAULT 'prd',
    source_channel VARCHAR(20) DEFAULT 'upload',
    external_url VARCHAR(500),
    version VARCHAR(20),
    author VARCHAR(100),
    publish_date DATE,
    domain VARCHAR(50),
    status VARCHAR(20) DEFAULT 'uploaded',
    raw_text TEXT,
    raw_image_path VARCHAR(500),
    parsed_sections JSONB,
    sections_count INTEGER,
    rules_count INTEGER,
    process_elapsed FLOAT,
    total_tokens INTEGER,
    vision_provider VARCHAR(20),
    llm_model VARCHAR(50),
    error_message VARCHAR(500),
    wiki_pages JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 2. 复制 prds 数据到 materials
INSERT INTO materials (id, title, filename, file_hash, version, author, publish_date,
    domain, doc_type, status, raw_text, parsed_sections, sections_count, rules_count,
    process_elapsed, total_tokens, vision_provider, llm_model, error_message, created_at)
SELECT id, title, filename, file_hash, version, author, publish_date,
    domain, doc_type, status, raw_text, parsed_sections, sections_count, rules_count,
    process_elapsed, total_tokens, vision_provider, llm_model, error_message, created_at
FROM prds;

-- 3. 创建 wiki_pages 表
CREATE TABLE wiki_pages (
    id SERIAL PRIMARY KEY,
    material_id INTEGER REFERENCES materials(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    page_type VARCHAR(30),
    page_path VARCHAR(300),
    markdown_content TEXT,
    structured_data JSONB,
    related_rules INTEGER[],
    related_pages INTEGER[],
    cross_references JSONB,
    version INTEGER DEFAULT 1,
    is_dirty BOOLEAN DEFAULT FALSE,
    last_generated_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- 4. 创建 wiki_logs 表
CREATE TABLE wiki_logs (
    id SERIAL PRIMARY KEY,
    operation VARCHAR(50),
    actor VARCHAR(100),
    target_type VARCHAR(30),
    target_id INTEGER,
    details JSONB,
    elapsed_seconds FLOAT,
    created_at TIMESTAMP DEFAULT NOW()
);

-- 5. 创建 wechat_work_messages 表
CREATE TABLE wechat_work_messages (
    id SERIAL PRIMARY KEY,
    msg_id VARCHAR(100) UNIQUE,
    msg_type VARCHAR(30),
    content TEXT,
    media_url VARCHAR(500),
    sender_id VARCHAR(100),
    sender_name VARCHAR(100),
    chat_id VARCHAR(100),
    status VARCHAR(20) DEFAULT 'received',
    material_id INTEGER REFERENCES materials(id),
    created_at TIMESTAMP DEFAULT NOW(),
    processed_at TIMESTAMP
);

-- 6. 添加 rules 表的 material_id 字段
ALTER TABLE rules ADD COLUMN material_id INTEGER REFERENCES materials(id) ON DELETE SET NULL;

-- 7. 更新 rules 的 material_id（从 prds 映射）
UPDATE rules SET material_id = prd_id WHERE prd_id IS NOT NULL;

-- 8. 创建索引
CREATE INDEX idx_materials_material_type ON materials(material_type);
CREATE INDEX idx_materials_source_channel ON materials(source_channel);
CREATE INDEX idx_wiki_pages_material_id ON wiki_pages(material_id);
CREATE INDEX idx_wiki_pages_page_type ON wiki_pages(page_type);
CREATE INDEX idx_wiki_logs_created_at ON wiki_logs(created_at);
CREATE INDEX idx_wechat_work_messages_msg_id ON wechat_work_messages(msg_id);
CREATE INDEX idx_wechat_work_messages_status ON wechat_work_messages(status);
CREATE INDEX idx_rules_material_id ON rules(material_id);