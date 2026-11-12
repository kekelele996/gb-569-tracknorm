-- tracknorm 初始结构（MySQL 8.0）
-- 说明：运行时由 SQLAlchemy `Base.metadata.create_all` 建表；本文件用于 DBA 审阅与手工初始化。

CREATE TABLE IF NOT EXISTS users (
  id INT AUTO_INCREMENT PRIMARY KEY,
  email VARCHAR(160) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  display_name VARCHAR(80) NOT NULL,
  role VARCHAR(20) NOT NULL,
  created_at DATETIME NOT NULL,
  INDEX ix_users_role (role)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS carriers (
  id INT AUTO_INCREMENT PRIMARY KEY,
  code VARCHAR(24) NOT NULL UNIQUE,
  name VARCHAR(60) NOT NULL,
  status_code_system VARCHAR(80) NOT NULL,
  api_base VARCHAR(160) NOT NULL,
  daily_quota INT NOT NULL DEFAULT 10000,
  rate_limit_per_min INT NOT NULL DEFAULT 60,
  avg_latency_ms FLOAT NOT NULL DEFAULT 180,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  note VARCHAR(255) NULL,
  last_pull_at DATETIME NULL,
  last_pull_stats JSON NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS waybills (
  id INT AUTO_INCREMENT PRIMARY KEY,
  waybill_no VARCHAR(40) NOT NULL UNIQUE,
  carrier_id INT NOT NULL,
  client_account VARCHAR(160) NOT NULL,
  client_ref VARCHAR(48) NOT NULL,
  origin_region VARCHAR(16) NOT NULL,
  dest_region VARCHAR(16) NOT NULL,
  origin_city VARCHAR(32) NOT NULL,
  dest_city VARCHAR(32) NOT NULL,
  service_level VARCHAR(16) NOT NULL DEFAULT 'standard',
  weight_kg FLOAT NOT NULL DEFAULT 1,
  trace_stage VARCHAR(24) NOT NULL DEFAULT 'created',
  current_status VARCHAR(24) NOT NULL DEFAULT 'created',
  promised_delivery_at DATETIME NOT NULL,
  collected_at DATETIME NOT NULL,
  last_event_at DATETIME NOT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT fk_waybills_carrier FOREIGN KEY (carrier_id) REFERENCES carriers (id),
  INDEX ix_waybills_carrier (carrier_id),
  INDEX ix_waybills_status (current_status),
  INDEX ix_waybills_client (client_account),
  INDEX ix_waybills_lane (origin_region, dest_region)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS trace_events (
  id INT AUTO_INCREMENT PRIMARY KEY,
  waybill_id INT NOT NULL,
  carrier_id INT NOT NULL,
  carrier_event_id VARCHAR(64) NOT NULL,
  raw_status VARCHAR(40) NOT NULL,
  seq INT NOT NULL DEFAULT 0,
  event_time DATETIME NOT NULL,
  location VARCHAR(64) NOT NULL,
  note VARCHAR(160) NULL,
  raw_payload JSON NULL,
  ingested_at DATETIME NOT NULL,
  CONSTRAINT uq_trace_waybill_event UNIQUE (waybill_id, carrier_event_id),
  CONSTRAINT fk_trace_waybill FOREIGN KEY (waybill_id) REFERENCES waybills (id),
  CONSTRAINT fk_trace_carrier FOREIGN KEY (carrier_id) REFERENCES carriers (id),
  INDEX ix_trace_event_time (event_time),
  INDEX ix_trace_raw_status (raw_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS status_mappings (
  id INT AUTO_INCREMENT PRIMARY KEY,
  version INT NOT NULL,
  carrier_code VARCHAR(24) NOT NULL DEFAULT '*',
  source_status VARCHAR(40) NOT NULL,
  target_status VARCHAR(24) NOT NULL,
  match_type VARCHAR(16) NOT NULL DEFAULT 'exact',
  score FLOAT NOT NULL DEFAULT 1,
  is_active TINYINT(1) NOT NULL DEFAULT 1,
  note VARCHAR(255) NULL,
  created_by VARCHAR(160) NULL,
  created_at DATETIME NOT NULL,
  CONSTRAINT uq_mapping_version_source UNIQUE (version, carrier_code, source_status),
  INDEX ix_mapping_version (version),
  INDEX ix_mapping_source (source_status),
  INDEX ix_mapping_target (target_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS normalized_tracks (
  id INT AUTO_INCREMENT PRIMARY KEY,
  waybill_id INT NOT NULL UNIQUE,
  mapping_version INT NOT NULL DEFAULT 1,
  current_status VARCHAR(24) NOT NULL,
  normalized_events JSON NULL,
  mapping_hits JSON NULL,
  conflicts JSON NULL,
  event_count INT NOT NULL DEFAULT 0,
  mapped_count INT NOT NULL DEFAULT 0,
  unmapped_count INT NOT NULL DEFAULT 0,
  duplicate_count INT NOT NULL DEFAULT 0,
  disorder_count INT NOT NULL DEFAULT 0,
  conflict_count INT NOT NULL DEFAULT 0,
  coverage FLOAT NOT NULL DEFAULT 0,
  last_event_time DATETIME NULL,
  computed_at DATETIME NOT NULL,
  CONSTRAINT fk_track_waybill FOREIGN KEY (waybill_id) REFERENCES waybills (id),
  INDEX ix_track_status (current_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS stagnation_alerts (
  id INT AUTO_INCREMENT PRIMARY KEY,
  waybill_id INT NOT NULL UNIQUE,
  carrier_id INT NOT NULL,
  lane_key VARCHAR(40) NOT NULL,
  stage VARCHAR(24) NOT NULL,
  baseline_p50_minutes FLOAT NOT NULL DEFAULT 0,
  baseline_mad_minutes FLOAT NOT NULL DEFAULT 0,
  baseline_samples INT NOT NULL DEFAULT 0,
  dwell_minutes FLOAT NOT NULL DEFAULT 0,
  robust_z FLOAT NOT NULL DEFAULT 0,
  severity VARCHAR(16) NOT NULL,
  predicted_delivery_at DATETIME NULL,
  promised_delivery_at DATETIME NULL,
  deviation_hours FLOAT NOT NULL DEFAULT 0,
  status VARCHAR(16) NOT NULL DEFAULT 'open',
  claimed_by VARCHAR(160) NULL,
  claimed_at DATETIME NULL,
  disposition VARCHAR(32) NULL,
  note TEXT NULL,
  detected_at DATETIME NOT NULL,
  handled_at DATETIME NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL,
  CONSTRAINT fk_alert_waybill FOREIGN KEY (waybill_id) REFERENCES waybills (id),
  CONSTRAINT fk_alert_carrier FOREIGN KEY (carrier_id) REFERENCES carriers (id),
  INDEX ix_alert_severity (severity),
  INDEX ix_alert_status (status),
  INDEX ix_alert_lane (lane_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS audit_logs (
  id INT AUTO_INCREMENT PRIMARY KEY,
  actor_email VARCHAR(160) NOT NULL,
  actor_role VARCHAR(20) NOT NULL,
  action VARCHAR(60) NOT NULL,
  entity VARCHAR(60) NOT NULL,
  entity_id VARCHAR(64) NULL,
  detail JSON NULL,
  layer VARCHAR(20) NOT NULL DEFAULT 'domain',
  ip VARCHAR(64) NULL,
  seed_key VARCHAR(120) NULL UNIQUE,
  created_at DATETIME NOT NULL,
  INDEX ix_audit_action (action),
  INDEX ix_audit_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
