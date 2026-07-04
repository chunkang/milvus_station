# ┌──────────────────────────────────────────────────────────────────────────┐
# │ milvus_station                                                           │
# │ Author  : Chun Kang <kurapa@kurapa.com>                                  │
# │ Created : 2026-07-03  (PDT, UTC-07:00)                                   │
# └──────────────────────────────────────────────────────────────────────────┘

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

-- ---------------------------------------------------------------------------
-- Sample source table for the embedding + vector-search pipeline.
--
-- Each row is a document whose `content` is turned into an embedding vector by
-- Llama (served via Ollama). That vector is stored + indexed in a Milvus
-- collection. `id` is the SHARED primary key that links a MariaDB row to its
-- vector in Milvus (Milvus stores `id` as the vector's primary key), so a
-- similarity hit in Milvus resolves straight back to the row here.
--
-- The embedding generation and the Milvus index build/search are implemented in
-- SPEC-SEARCH-002. This table is the scaffolded data source that pipeline reads.
-- ---------------------------------------------------------------------------
USE `milvus_station`;

CREATE TABLE IF NOT EXISTS `documents` (
  `id`               BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  `title`            VARCHAR(255)    NOT NULL,
  `content`          TEXT            NOT NULL,               -- text that gets embedded
  `source`           VARCHAR(255)    DEFAULT NULL,           -- provenance / origin tag
  `embedding_model`  VARCHAR(128)    DEFAULT NULL,           -- e.g. 'nomic-embed-text'
  `embedding_dim`    INT UNSIGNED    DEFAULT NULL,           -- vector dimensionality
  `embedding_status` ENUM('pending','embedded','failed') NOT NULL DEFAULT 'pending',
  `milvus_pk`        BIGINT UNSIGNED DEFAULT NULL,           -- primary key of the vector in Milvus (mirrors `id` once indexed)
  `content_hash`     CHAR(64)        DEFAULT NULL,           -- sha256(content) for dedupe / change detection
  `created_at`       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       TIMESTAMP       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (`id`),
  KEY `idx_embedding_status` (`embedding_status`),         -- find rows still needing embeddings
  KEY `idx_milvus_pk` (`milvus_pk`),                       -- resolve a Milvus hit back to its row
  UNIQUE KEY `uq_content_hash` (`content_hash`)            -- avoid embedding duplicate content twice
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- A few sample documents so the SPEC-SEARCH-002 pipeline has data to embed and
-- index on first boot. INSERT IGNORE + unique content_hash keeps this idempotent.
INSERT IGNORE INTO `documents` (`title`, `content`, `source`, `content_hash`) VALUES
  ('Milvus overview',
   'Milvus is an open-source vector database that stores embeddings and performs fast approximate nearest-neighbor search using indexes such as IVF_FLAT and HNSW.',
   'seed', SHA2('Milvus is an open-source vector database that stores embeddings and performs fast approximate nearest-neighbor search using indexes such as IVF_FLAT and HNSW.', 256)),
  ('Llama embeddings',
   'Llama models served through Ollama can generate dense vector embeddings from text, which downstream systems index for semantic similarity search.',
   'seed', SHA2('Llama models served through Ollama can generate dense vector embeddings from text, which downstream systems index for semantic similarity search.', 256)),
  ('MariaDB as source of truth',
   'MariaDB holds the canonical document text and metadata; Milvus holds only the vectors, linked back to MariaDB rows by a shared primary key.',
   'seed', SHA2('MariaDB holds the canonical document text and metadata; Milvus holds only the vectors, linked back to MariaDB rows by a shared primary key.', 256)),
  ('Vector search flow',
   'A query is embedded with the same Llama model, Milvus returns the nearest vector primary keys, and those keys fetch the original documents from MariaDB.',
   'seed', SHA2('A query is embedded with the same Llama model, Milvus returns the nearest vector primary keys, and those keys fetch the original documents from MariaDB.', 256));
