-- Ardayda Database Schema

-- users table
CREATE TABLE users (
    user_id INTEGER PRIMARY KEY,
    full_name TEXT,
    region TEXT,
    school_name TEXT,
    user_class TEXT,
    status TEXT DEFAULT 'menu:home',
    is_admin INTEGER DEFAULT 0,
    suspended INTEGER DEFAULT 0,
    joined_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- pdfs table
CREATE TABLE pdfs (
    pdf_id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_id TEXT NOT NULL,
    file_unique_id TEXT UNIQUE NOT NULL,
    pdf_name TEXT NOT NULL,
    subject TEXT NOT NULL,
    uploader_id INTEGER NOT NULL,
    download_count INTEGER DEFAULT 0,
    upload_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (uploader_id) REFERENCES users(user_id) ON DELETE CASCADE
);

-- pdf_tags table
CREATE TABLE pdf_tags (
    pdf_id INTEGER NOT NULL,
    tag_name TEXT NOT NULL,
    PRIMARY KEY (pdf_id, tag_name),
    FOREIGN KEY (pdf_id) REFERENCES pdfs(pdf_id) ON DELETE CASCADE
);

-- ardayda_admin_logs table
CREATE TABLE ardayda_admin_logs (
    log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id INTEGER NOT NULL,
    action_performed TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_id INTEGER NOT NULL,
    extra_details TEXT,
    action_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_pdfs_subject ON pdfs(subject);
CREATE INDEX idx_pdfs_uploader ON pdfs(uploader_id);
CREATE INDEX idx_tags_pdf ON pdf_tags(pdf_id);
