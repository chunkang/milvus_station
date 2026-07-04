-- SPEC-INFRA-001 / U2: seed the application schema and grant the milvus user
-- full privileges. Runs once, on an empty data directory, via
-- /docker-entrypoint-initdb.d. Idempotent so a re-run is harmless.
--
-- The MARIADB_DATABASE / MARIADB_USER / MARIADB_PASSWORD env vars already
-- create the database and the milvus/milvus user; this script guarantees the
-- database exists and that the user holds ALL PRIVILEGES on it.

CREATE DATABASE IF NOT EXISTS `milvus_station`
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'milvus'@'%' IDENTIFIED BY 'milvus';

GRANT ALL PRIVILEGES ON `milvus_station`.* TO 'milvus'@'%';

FLUSH PRIVILEGES;
