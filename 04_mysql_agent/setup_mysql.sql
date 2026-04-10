-- ============================================================
-- MySQL Setup Script for ADK Session Store (v1 schema)
-- Schema sourced from: google.adk.sessions.schemas.v1
--
-- Run via Docker:
--   docker exec -i adk-mysql mysql -u root -proot123 adk_sessions < setup_mysql.sql
-- Or mysql client:
--   mysql -u root -proot123 adk_sessions < setup_mysql.sql
-- ============================================================

CREATE DATABASE IF NOT EXISTS adk_sessions
    CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

USE adk_sessions;

-- Drop all existing tables cleanly
SET FOREIGN_KEY_CHECKS=0;
DROP TABLE IF EXISTS events;
DROP TABLE IF EXISTS sessions;
DROP TABLE IF EXISTS app_states;
DROP TABLE IF EXISTS user_states;
DROP TABLE IF EXISTS adk_internal_metadata;
SET FOREIGN_KEY_CHECKS=1;

-- ============================================================
-- adk_internal_metadata
-- ADK reads this FIRST to detect schema version.
-- schema_version='1' → use v1 JSON serialization (event_data column).
-- If this table is missing, ADK falls back to v0 Pickle detection → error.
-- ============================================================
CREATE TABLE adk_internal_metadata (
    `key`   VARCHAR(128) NOT NULL,
    value   VARCHAR(256) NOT NULL,
    PRIMARY KEY (`key`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO adk_internal_metadata (`key`, value) VALUES ('schema_version', '1');

-- ============================================================
-- sessions
-- VARCHAR(128) = ADK DEFAULT_MAX_KEY_LENGTH
-- LONGTEXT     = ADK DynamicJSON on MySQL
-- ============================================================
CREATE TABLE sessions (
    id          VARCHAR(128) NOT NULL,
    app_name    VARCHAR(128) NOT NULL,
    user_id     VARCHAR(128) NOT NULL,
    state       LONGTEXT,
    create_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                      ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (app_name, user_id, id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- events (ADK v1: all event data stored in single event_data JSON blob)
-- ============================================================
CREATE TABLE events (
    id            VARCHAR(128) NOT NULL,
    app_name      VARCHAR(128) NOT NULL,
    user_id       VARCHAR(128) NOT NULL,
    session_id    VARCHAR(128) NOT NULL,
    invocation_id VARCHAR(256) NOT NULL DEFAULT '',
    timestamp     DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6),
    event_data    LONGTEXT,
    PRIMARY KEY (app_name, user_id, session_id, id),
    CONSTRAINT fk_events_session
        FOREIGN KEY (app_name, user_id, session_id)
        REFERENCES sessions (app_name, user_id, id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================
-- app_states & user_states
-- ============================================================
CREATE TABLE app_states (
    app_name    VARCHAR(128) NOT NULL,
    state       LONGTEXT,
    update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                      ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (app_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE user_states (
    app_name    VARCHAR(128) NOT NULL,
    user_id     VARCHAR(128) NOT NULL,
    state       LONGTEXT,
    update_time DATETIME(6)  NOT NULL DEFAULT CURRENT_TIMESTAMP(6)
                                      ON UPDATE CURRENT_TIMESTAMP(6),
    PRIMARY KEY (app_name, user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Verify
SHOW TABLES;
SELECT * FROM adk_internal_metadata;
