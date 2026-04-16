CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE prds (
    id SERIAL PRIMARY KEY,
    title VARCHAR(200) NOT NULL,
    filename VARCHAR(300) NOT NULL,
    file_hash VARCHAR(32) UNIQUE,
    version VARCHAR(20),
    author VARCHAR(100),
    publish_date DATE,
    domain VARCHAR(50),
    status VARCHAR(20) DEFAULT 'parsing',
    raw_text TEXT,
    parsed_sections JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE rules (
    id SERIAL PRIMARY KEY,
    prd_id INTEGER REFERENCES prds(id) ON DELETE CASCADE,
    domain VARCHAR(50),
    category VARCHAR(100),
    rule_text TEXT NOT NULL,
    structured_logic JSONB,
    params JSONB,
    involves_roles TEXT[],
    compliance_notes TEXT[],
    source_section VARCHAR(200),
    risk_score REAL DEFAULT 0,
    risk_flags TEXT[],
    status VARCHAR(20) DEFAULT 'draft',
    hit_count INTEGER DEFAULT 0,
    last_hit_at TIMESTAMP,
    embedding vector(768),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE challenges (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES rules(id) ON DELETE CASCADE,
    challenger VARCHAR(100),
    content TEXT NOT NULL,
    resolution TEXT,
    status VARCHAR(20) DEFAULT 'open',
    created_at TIMESTAMP DEFAULT NOW(),
    resolved_at TIMESTAMP
);

CREATE TABLE audit_logs (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES rules(id) ON DELETE CASCADE,
    actor VARCHAR(100),
    action VARCHAR(50),
    diff JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE rule_relations (
    id SERIAL PRIMARY KEY,
    source_rule_id INTEGER REFERENCES rules(id) ON DELETE CASCADE,
    target_rule_id INTEGER REFERENCES rules(id) ON DELETE CASCADE,
    relation_type VARCHAR(30),
    description TEXT
);

CREATE TABLE rule_sources (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER NOT NULL REFERENCES rules(id) ON DELETE CASCADE,
    prd_id INTEGER NOT NULL REFERENCES prds(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(rule_id, prd_id)
);

CREATE INDEX idx_rules_domain ON rules(domain);
CREATE INDEX idx_rules_category ON rules(category);
CREATE INDEX idx_rules_status ON rules(status);
CREATE INDEX idx_rules_prd_id ON rules(prd_id);
CREATE INDEX idx_challenges_rule_id ON challenges(rule_id);
CREATE INDEX idx_audit_logs_rule_id ON audit_logs(rule_id);
