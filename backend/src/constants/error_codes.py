"""统一错误码，前端 utils/errorMessage.ts 兜底文案与之对应。"""
from __future__ import annotations

ERROR_CODES: dict[str, str] = {
    "AUTH_INVALID": "邮箱或密码不正确",
    "AUTH_MISSING": "缺少或无效的访问令牌",
    "FORBIDDEN": "当前角色无权执行该操作",
    "NOT_FOUND": "对象不存在",
    "CONFLICT": "对象状态冲突",
    "ALERT_STATE_CONFLICT": "预警已被他人认领或已处置",
    "MAPPING_VERSION_CONFLICT": "映射版本已存在或不可用",
    "RATE_LIMITED": "请求过于频繁，请稍后再试",
    "CARRIER_RATE_LIMITED": "承运商接口限流，已自动退避重试",
    "INSUFFICIENT_BASELINE": "该线路基线样本不足，无法判定停滞",
    "VALIDATION": "请求参数不合法",
    "INTERNAL": "服务内部错误",
}
