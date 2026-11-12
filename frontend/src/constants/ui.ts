export const BRAND = {
  name: 'tracknorm',
  cn: '迅联供应链 · 轨迹归一与停滞预警台',
  tagline: 'TRACK NORMALIZE / STAGNATION RADAR',
};

export interface NavItem {
  to: string;
  label: string;
  hint: string;
  permission: string;
}

export const NAV_ITEMS: NavItem[] = [
  { to: '/waybills', label: '运单总览', hint: '200 单 · 8 状态', permission: 'waybill:read' },
  { to: '/mappings', label: '映射规则', hint: '码表版本', permission: 'mapping:read' },
  { to: '/alerts', label: '停滞预警', hint: '雷达屏', permission: 'alert:read' },
  { to: '/carriers', label: '承运商与质量', hint: '配额 / 报表', permission: 'carrier:read' },
];

export const STATUS_BUCKET_HINT = '按归一状态分桶 · 点击筛选';
