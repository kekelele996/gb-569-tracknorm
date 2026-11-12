import { Navigate, useLocation } from 'react-router-dom';
import { useSyncExternalStore } from 'react';
import { authStore } from '../stores/authStore';
import { can, ROLE_LABEL } from '../constants/roles';
import type { Role } from '../types/models';

export function useAuth() {
  return useSyncExternalStore(authStore.subscribe, authStore.getState);
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const state = useAuth();
  const location = useLocation();
  if (!state.bootstrapped) {
    return <div className="main" style={{ padding: 40 }}>正在恢复登录态 …</div>;
  }
  if (!state.token) {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  return <>{children}</>;
}

export function RequirePermission({ permission, children }: { permission: string; children: React.ReactNode }) {
  const state = useAuth();
  const role = (state.user?.role ?? undefined) as Role | undefined;
  if (!state.user || !can(role, permission)) {
    return (
      <div className="forbidden" data-testid="forbidden">
        <div>
          <div className="eyebrow">403 · FORBIDDEN</div>
          <h1>这页不在你的权限范围</h1>
          <p className="soft" style={{ maxWidth: 440 }}>
            当前角色 {role ? ROLE_LABEL[role] : '访客'} 只能查看自己名下运单轨迹与延迟说明 CSV；
            映射版本、承运商配置与预警处置需要客服专员或运营主管权限，后端接口同样返回 403。
          </p>
        </div>
      </div>
    );
  }
  return <>{children}</>;
}
