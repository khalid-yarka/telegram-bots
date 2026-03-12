-- Master Database Schema
-- Tables for master bot system

-- 1. system_bots table
CREATE TABLE system_bots (
    bot_token TEXT PRIMARY KEY,
    bot_name TEXT NOT NULL,
    bot_type TEXT NOT NULL,
    owner_id INTEGER NOT NULL,
    is_active INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bot_username TEXT,
    last_seen TIMESTAMP,
    total_users INTEGER DEFAULT 0,
    total_messages INTEGER DEFAULT 0
);

-- 2. bot_permissions table
CREATE TABLE bot_permissions (
    bot_token TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    permission_level TEXT NOT NULL,
    granted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    granted_by INTEGER,
    notes TEXT,
    PRIMARY KEY (bot_token, user_id),
    FOREIGN KEY (bot_token) REFERENCES system_bots(bot_token) ON DELETE CASCADE
);

-- 3. system_logs table
CREATE TABLE system_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    bot_token TEXT,
    user_id INTEGER,
    action_type TEXT NOT NULL,
    details TEXT,
    FOREIGN KEY (bot_token) REFERENCES system_bots(bot_token) ON DELETE SET NULL
);

-- Indexes for better performance
CREATE INDEX idx_logs_bot ON system_logs(bot_token);
CREATE INDEX idx_logs_user ON system_logs(user_id);
CREATE INDEX idx_logs_time ON system_logs(timestamp);
CREATE INDEX idx_permissions_user ON bot_permissions(user_id);
