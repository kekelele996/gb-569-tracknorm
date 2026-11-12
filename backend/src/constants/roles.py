"""角色 -> 权限点映射，README 与前端 constants/roles.ts 同步。"""
from __future__ import annotations

from src.constants.enums import Role

ROLE_LABELS: dict[str, str] = {
    Role.ADMIN.value: "运营主管",
    Role.OPS.value: "客服专员",
    Role.CLIENT.value: "商家（只读）",
}

PERMISSIONS: dict[str, set[str]] = {
    Role.ADMIN.value: {
        "carrier:read", "carrier:write",
        "waybill:read", "track:read", "track:pull", "track:normalize",
        "mapping:read", "mapping:write",
        "alert:read", "alert:handle",
        "report:read", "report:export", "report:audit",
    },
    Role.OPS.value: {
        "carrier:read", "waybill:read", "track:read", "track:pull", "track:normalize",
        "mapping:read", "alert:read", "alert:handle", "report:read", "report:export",
    },
    Role.CLIENT.value: {
        "waybill:read", "track:read", "report:export",
    },
}

# 写接口角色白名单（controller 层使用）
CARRIER_WRITE_ROLES = (Role.ADMIN.value,)
TRACK_RUN_ROLES = (Role.ADMIN.value, Role.OPS.value)
MAPPING_WRITE_ROLES = (Role.ADMIN.value,)
ALERT_HANDLE_ROLES = (Role.ADMIN.value, Role.OPS.value)
QUALITY_READ_ROLES = (Role.ADMIN.value, Role.OPS.value)
AUDIT_READ_ROLES = (Role.ADMIN.value,)


def has_permission(role: str, permission: str) -> bool:
    return permission in PERMISSIONS.get(role, set())
