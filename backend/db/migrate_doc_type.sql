-- Add doc_type column to prds table
ALTER TABLE prds ADD COLUMN IF NOT EXISTS doc_type VARCHAR(20) DEFAULT 'prd';
