-- ─────────────────────────────────────────────
-- CloudApp Database Schema
-- Run on MySQL DB Instance (DB Private Subnet)
-- ─────────────────────────────────────────────

CREATE DATABASE IF NOT EXISTS appdb CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE appdb;

CREATE TABLE IF NOT EXISTS users (
    id            INT UNSIGNED    NOT NULL AUTO_INCREMENT,
    username      VARCHAR(50)     NOT NULL,
    email         VARCHAR(255)    NOT NULL UNIQUE,
    password_hash VARCHAR(255)    NOT NULL,
    created_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at    DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    is_active     TINYINT(1)      NOT NULL DEFAULT 1,
    PRIMARY KEY (id),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- App user for Flask (limited privileges)
CREATE USER IF NOT EXISTS 'appuser'@'%' IDENTIFIED BY 'StrongPass123!';
GRANT SELECT, INSERT, UPDATE ON appdb.users TO 'appuser'@'%';
FLUSH PRIVILEGES;
EXIT;

OR

DROP USER IF EXISTS 'appuser'@'%';
CREATE USER 'appuser'@'%' IDENTIFIED BY 'StrongPass123!';
GRANT SELECT, INSERT, UPDATE ON appdb.* TO 'appuser'@'%';
FLUSH PRIVILEGES;
EXIT;

