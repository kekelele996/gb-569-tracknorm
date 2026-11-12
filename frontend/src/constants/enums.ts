/** 与后端 src/constants/enums.py 保持一致的共享枚举（README 列出全部出现位置）。 */

export interface StatusMeta {
  value: string;
  label: string;
  tone: 'neutral' | 'moving' | 'ok' | 'warn' | 'danger';
  hint: string;
}

export const NORMALIZED_STATUSES: StatusMeta[] = [
  { value: 'created', label: '已下单', tone: 'neutral', hint: '已接单待揽收' },
  { value: 'collected', label: '已揽收', tone: 'moving', hint: '承运商已揽件' },
  { value: 'in_transit', label: '运输中', tone: 'moving', hint: '干线运输' },
  { value: 'arrived_hub', label: '到达分拨', tone: 'moving', hint: '到达目的地分拨' },
  { value: 'out_for_delivery', label: '派送中', tone: 'warn', hint: '末端派送' },
  { value: 'delivered', label: '已签收', tone: 'ok', hint: '签收完成' },
  { value: 'exception', label: '异常', tone: 'danger', hint: '异常件' },
  { value: 'returning', label: '退件', tone: 'danger', hint: '退件流程' },
];

export const STATUS_ORDER = NORMALIZED_STATUSES.map((item) => item.value);

export const STATUS_LABEL: Record<string, string> = Object.fromEntries(
  NORMALIZED_STATUSES.map((item) => [item.value, item.label]),
);

export const STATUS_TONE: Record<string, StatusMeta['tone']> = Object.fromEntries(
  NORMALIZED_STATUSES.map((item) => [item.value, item.tone]),
);

export const MATCH_TYPES: { value: string; label: string }[] = [
  { value: 'exact', label: '精确' },
  { value: 'alias', label: '别名' },
  { value: 'fuzzy', label: '模糊' },
];

export const MATCH_TYPE_LABEL: Record<string, string> = Object.fromEntries(
  MATCH_TYPES.map((item) => [item.value, item.label]),
);

export const ALERT_SEVERITIES: { value: string; label: string; hint: string }[] = [
  { value: 'critical', label: '严重', hint: 'z ≥ 8' },
  { value: 'alert', label: '预警', hint: 'z 5–8' },
  { value: 'warn', label: '关注', hint: 'z 3.5–5' },
];

export const SEVERITY_LABEL: Record<string, string> = Object.fromEntries(
  ALERT_SEVERITIES.map((item) => [item.value, item.label]),
);

export const ALERT_STATUSES = [
  { value: 'open', label: '待认领' },
  { value: 'claimed', label: '已认领' },
  { value: 'handled', label: '已处置' },
  { value: 'dismissed', label: '误报关闭' },
];

export const ALERT_STATUS_LABEL: Record<string, string> = Object.fromEntries(
  ALERT_STATUSES.map((item) => [item.value, item.label]),
);

export const DISPOSITIONS = [
  { value: 'contacting', label: '已联系客户说明' },
  { value: 'transfer', label: '转承运商核查' },
  { value: 'exception_confirmed', label: '确认异常件' },
  { value: 'resend', label: '安排补发' },
  { value: 'dismissed', label: '误报关闭' },
];

export const DISPOSITION_LABEL: Record<string, string> = Object.fromEntries(
  DISPOSITIONS.map((item) => [item.value, item.label]),
);

export const SERVICE_LEVEL_LABEL: Record<string, string> = {
  standard: '标准件',
  express: '加急件',
  bulky: '大件',
};

export const Z_THRESHOLDS = { warn: 3.5, alert: 5, critical: 8 };
