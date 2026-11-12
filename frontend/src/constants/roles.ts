/** 角色权限点：与后端 src/constants/roles.py 同步（README 列出全部出现位置）。 */
import type { Role } from '../types/models';

export const ROLE_LABEL: Record<Role, string> = {
  admin: '运营主管',
  ops: '客服专员',
  client: '商家（只读）',
};

export const PERMISSIONS: Record<Role, string[]> = {
  admin: [
    'carrier:read', 'carrier:write',
    'waybill:read', 'track:read', 'track:pull', 'track:normalize',
    'mapping:read', 'mapping:write',
    'alert:read', 'alert:handle',
    'report:read', 'report:export', 'report:audit',
  ],
  ops: [
    'carrier:read', 'waybill:read', 'track:read', 'track:pull', 'track:normalize',
    'mapping:read', 'alert:read', 'alert:handle', 'report:read', 'report:export',
  ],
  client: ['waybill:read', 'track:read', 'report:export'],
};

export function can(role: Role | undefined, permission: string): boolean {
  if (!role) return false;
  return PERMISSIONS[role]?.includes(permission) ?? false;
}
