const CODE_MESSAGE: Record<string, string> = {
  AUTH_INVALID: '邮箱或密码不正确',
  AUTH_MISSING: '登录已过期，请重新登录',
  FORBIDDEN: '当前角色无权执行该操作（后端 403）',
  NOT_FOUND: '对象不存在',
  CONFLICT: '对象状态冲突，请刷新后重试',
  ALERT_STATE_CONFLICT: '该预警已被他人认领或已处置',
  MAPPING_VERSION_CONFLICT: '映射版本已存在或不可用',
  RATE_LIMITED: '操作过于频繁，请稍后再试',
  CARRIER_RATE_LIMITED: '承运商接口限流，已自动退避重试',
  INSUFFICIENT_BASELINE: '该线路基线样本不足，无法判定停滞',
  VALIDATION: '提交内容不合法',
  INTERNAL: '服务内部错误，请稍后重试',
};

export function errorMessage(payload: unknown, fallback = '请求失败'): string {
  if (!payload || typeof payload !== 'object') return fallback;
  const data = payload as { code?: string; message?: string; detail?: unknown };
  if (data.code && CODE_MESSAGE[data.code]) {
    const detail = data.detail ? `（${String(data.detail)}）` : '';
    return `${CODE_MESSAGE[data.code]}${detail}`;
  }
  return data.message || fallback;
}
