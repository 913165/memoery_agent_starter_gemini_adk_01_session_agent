-- ============================================================
-- MySQL Setup Script for ADK Session Store (v1 schema)
-- Run this script in your local MySQL client:
--   mysql -u root -p < setup_mysql.sql
-- Or paste it directly into MySQL Workbench / DBeaver / phpMyAdmin
-- ============================================================

-- 1. Create the database if it doesn't already exist
CREATE DATABASE IF NOT EXISTS adk_sessions
    CHARACTER SET utf8mb4
    COLLATE utf8mb4_unicode_ci;

-- 2. Switch to the new database
USE adk_sessions;

-- 3. (Optional) Create a dedicated user instead of using root.
--    Replace 'adk_user' and 'adk_password' with your own values,
--    then update MYSQL_USER / MYSQL_PASSWORD in your .env file.
-- Uncomment the lines below if you want a dedicated DB user:
-- CREATE USER IF NOT EXISTS 'adk_user'@'localhost' IDENTIFIED BY 'adk_password';
-- GRANT ALL PRIVILEGES ON adk_sessions.* TO 'adk_user'@'localhost';
-- FLUSH PRIVILEGES;

-- ============================================================
-- 4. DROP old tables if they exist (clean slate)
-- ============================================================
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS sessions;

-- ============================================================
-- 5. Create tables using ADK v1 schema
-- NOTE: VARCHAR(191) on key columns because utf8mb4 = 4 bytes/char.
--   sessions: 3 cols * 191 * 4 = 2292 bytes  < 3072 byte limit
--   events:   4 cols * 191 * 4 = 3056 bytes  < 3072 byte limit
-- ============================================================

-- sessions table
CREATE TABLE sessions (
    id            VARCHAR(191)  NOT NULL,
    app_name      VARCHAR(191)  NOT NULL,
    user_id       VARCHAR(191)  NOT NULL,
    state         JSON,
    create_time   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    update_time   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                         ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (app_name, user_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- events table (full ADK v1 schema)
CREATE TABLE events (
    id                          VARCHAR(191)  NOT NULL,
    app_name                    VARCHAR(191)  NOT NULL,
    user_id                     VARCHAR(191)  NOT NULL,
    session_id                  VARCHAR(191)  NOT NULL,
    invocation_id               VARCHAR(191)  NOT NULL DEFAULT '',
    author                      VARCHAR(255),
    actions                     JSON,
    long_running_tool_ids_json  JSON,
    branch                      VARCHAR(255),
    timestamp                   DATETIME(6)   NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    content                     JSON,
    grounding_metadata          JSON,
    custom_metadata             JSON,
    usage_metadata              JSON,
    citation_metadata           JSON,
    partial                     TINYINT(1),
    turn_complete               TINYINT(1),
    error_code                  VARCHAR(255),
    error_message               TEXT,
    interrupted                 TINYINT(1),
    input_transcription         JSON,
    output_transcription        JSON,
    PRIMARY KEY (app_name, user_id, session_id, id),
    CONSTRAINT fk_events_session
        FOREIGN KEY (app_name, user_id, session_id)
        REFERENCES sessions (app_name, user_id, id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- 6. Quick sanity-check: list tables and columns
-- ============================================================
SHOW TABLES;
DESCRIBE sessions;
DESCRIBE events;

-- ============================================================
-- Done!  Now update your .env file:
--   MYSQL_USER=root
--   MYSQL_PASSWORD=root123
--   MYSQL_HOST=127.0.0.1
--   MYSQL_PORT=3306
--   MYSQL_DATABASE=adk_sessions
-- Then run:  python main.py
-- ============================================================
