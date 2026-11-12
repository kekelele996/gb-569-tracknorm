export type Role = 'admin' | 'ops' | 'client';

export interface UserInfo {
  id: number;
  email: string;
  display_name: string;
  role: Role;
  role_label: string;
}

export interface Bucket {
  status: string;
  label: string;
  count: number;
}

export interface Waybill {
  id: number;
  waybill_no: string;
  carrier_id: number;
  carrier_code: string;
  carrier_name: string;
  client_account: string;
  client_ref: string;
  lane: string;
  origin_region: string;
  dest_region: string;
  origin_city: string;
  dest_city: string;
  service_level: string;
  service_level_label: string;
  weight_kg: number;
  current_status: string;
  current_status_label: string;
  trace_stage: string;
  trace_stage_label: string;
  promised_delivery_at: string | null;
  collected_at: string | null;
  last_event_at: string | null;
  coverage: number;
  conflict_count: number;
  mapping_version: number | null;
  event_count: number;
}

export interface WaybillList {
  items: Waybill[];
  buckets: Bucket[];
  total: number;
  page: number;
  size: number;
  carriers?: { code: string; name: string }[];
}

export interface RawEvent {
  id: number;
  carrier_event_id: string;
  raw_status: string;
  seq: number;
  event_time: string | null;
  location: string;
  note: string | null;
  raw_payload: Record<string, unknown>;
}

export interface TrackEvent {
  carrier_event_id: string;
  raw_status: string;
  target_status?: string;
  target_label?: string;
  match_type?: string;
  score?: number;
  event_time: string | null;
  location: string;
  seq: number;
  note?: string | null;
}

export interface ConflictItem {
  carrier_event_id: string;
  raw_status: string;
  event_time: string | null;
  location: string;
  from_status: string;
  to_status: string;
  reason: string;
  reason_label: string;
}

export interface MappingHit {
  rule_id: number | null;
  source_status: string;
  target_status: string;
  match_type: string;
  score: number;
  hits: number;
  conflicts: number;
}

export interface WaybillDetail {
  waybill: Waybill;
  events: RawEvent[];
  normalized_events: TrackEvent[];
  mapping_hits: MappingHit[];
  conflicts: ConflictItem[];
  coverage: number;
  mapping_version: number | null;
  duplicate_count: number;
  disorder_count: number;
  unmapped_count: number;
  alert_id: number | null;
  alert_severity: string | null;
  alert_status: string | null;
}

export interface Carrier {
  id: number;
  code: string;
  name: string;
  status_code_system: string;
  api_base: string;
  daily_quota: number;
  rate_limit_per_min: number;
  avg_latency_ms: number;
  is_active: boolean;
  note: string | null;
  last_pull_at: string | null;
  last_pull_stats: Record<string, unknown>;
  waybill_count: number;
}

export interface MappingRule {
  id: number;
  version: number;
  carrier_code: string;
  source_status: string;
  target_status: string;
  target_label: string;
  match_type: string;
  score: number;
  is_active: boolean;
  note: string | null;
  hits: number;
  conflicts: number;
  created_at: string | null;
}

export interface MappingVersion {
  version: number;
  rules: number;
  created_at: string | null;
  is_active: boolean;
}

export interface MappingRuleList {
  version: number;
  active_version: number;
  rules: MappingRule[];
}

export interface MappingConflict {
  waybill_id: number;
  waybill_no: string;
  carrier_code: string;
  raw_status: string;
  from_status: string;
  to_status: string;
  event_time: string | null;
  reason_label: string;
}

export interface MappingStats {
  version: number;
  coverage: number;
  coverage_percent: number;
  conflicts: number;
  unmapped_events: number;
  events: number;
  by_status: Bucket[];
  conflict_items: MappingConflict[];
  duration_ms: number;
}

export interface Alert {
  id: number;
  waybill_id: number;
  waybill_no: string;
  client_account: string;
  client_ref: string;
  carrier_code: string;
  carrier_name: string;
  lane_key: string;
  origin_city: string;
  dest_city: string;
  stage: string;
  stage_label: string;
  baseline_p50_minutes: number;
  baseline_mad_minutes: number;
  baseline_samples: number;
  dwell_minutes: number;
  robust_z: number;
  severity: string;
  status: string;
  claimed_by: string | null;
  claimed_at: string | null;
  disposition: string | null;
  disposition_label: string | null;
  note: string | null;
  predicted_delivery_at: string | null;
  promised_delivery_at: string | null;
  deviation_hours: number;
  detected_at: string | null;
  handled_at: string | null;
  timeline: TrackEvent[];
}

export interface AlertSummary {
  total: number;
  by_severity: Record<string, number>;
  by_status: Record<string, number>;
  lane_count: number;
}

export interface QualityRow {
  carrier_id: number;
  carrier_code: string;
  carrier_name: string;
  status_code_system: string;
  waybills: number;
  events: number;
  mapped_events: number;
  unmapped_events: number;
  duplicate_events: number;
  disorder_events: number;
  conflict_events: number;
  coverage: number;
  coverage_percent: number;
  duplicate_rate: number;
  conflict_rate: number;
  quality_score: number;
  rate_limit_hits: number;
  last_pull_at: string | null;
  is_active: boolean;
  daily_quota: number;
  rate_limit_per_min: number;
}

export interface PullStats {
  waybills: number;
  carriers: { carrier_code: string; carrier_name: string; waybills: number; events_fetched: number; inserted: number; last_pull_at: string | null }[];
  events_fetched: number;
  events_inserted: number;
  events_unchanged: number;
  rate_limit_hits: number;
  backoff_ms: number[];
  duration_ms: number;
  pulled_at: string;
  mock_boundary?: string;
}

export interface NormalizeStats {
  version: number;
  active_version: number;
  waybills: number;
  events: number;
  mapped_events: number;
  unmapped_events: number;
  duplicates: number;
  disorder: number;
  conflicts: number;
  coverage: number;
  coverage_percent: number;
  by_status: Bucket[];
  conflict_items: MappingConflict[];
  duration_ms: number;
  computed_at: string;
  stagnation?: Record<string, unknown>;
}

export interface LastRuns {
  pull: PullStats | null;
  normalize: NormalizeStats | null;
}

export interface AuditLog {
  id: number;
  actor_email: string;
  actor_role: string;
  action: string;
  action_label: string;
  entity: string;
  entity_id: string | null;
  detail: Record<string, unknown>;
  layer: string;
  created_at: string | null;
}
