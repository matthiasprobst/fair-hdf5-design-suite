CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    is_admin INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS local_credentials (
    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    password_hash TEXT NOT NULL,
    must_change INTEGER NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
    csrf_token TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS sessions_user ON sessions(user_id);
CREATE TABLE IF NOT EXISTS login_attempts (
    username TEXT NOT NULL,
    address TEXT NOT NULL,
    attempted_at REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS login_attempts_time ON login_attempts(attempted_at);
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    owner_id TEXT NOT NULL REFERENCES users(id),
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    blueprint TEXT NOT NULL,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    import_key TEXT,
    UNIQUE(owner_id, import_key)
);
CREATE TABLE IF NOT EXISTS project_members (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(id),
    role TEXT NOT NULL CHECK(role IN ('editor', 'viewer')),
    PRIMARY KEY(project_id, user_id)
);
CREATE TABLE IF NOT EXISTS edit_locks (
    project_id TEXT PRIMARY KEY REFERENCES projects(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    editor_id TEXT NOT NULL,
    token_hash TEXT NOT NULL,
    expires_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS project_templates (
    project_id TEXT NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    template_id TEXT NOT NULL,
    revision INTEGER NOT NULL,
    snapshot TEXT NOT NULL,
    PRIMARY KEY(project_id, template_id, revision)
);
