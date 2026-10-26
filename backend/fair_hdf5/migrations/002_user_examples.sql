CREATE TABLE user_examples (
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    example_id TEXT NOT NULL,
    project_id TEXT UNIQUE REFERENCES projects(id) ON DELETE SET NULL,
    created_at REAL NOT NULL,
    PRIMARY KEY (user_id, example_id)
);
