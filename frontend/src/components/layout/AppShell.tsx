import { NavLink, useNavigate } from 'react-router-dom';
import { useSyncExternalStore } from 'react';
import { authStore } from '../../stores/authStore';
import { can, ROLE_LABEL } from '../../constants/roles';
import { BRAND, NAV_ITEMS } from '../../constants/ui';
import type { Role } from '../../types/models';
import Toasts from '../common/Toasts';
import { useAsync } from '../../hooks/useAsync';
import { tracksApi } from '../../api/tracks';
import { fmtTime } from '../../utils/format';

export default function AppShell({ children }: { children: React.ReactNode }) {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const navigate = useNavigate();
  const role = state.user?.role as Role | undefined;
  const navItems = NAV_ITEMS.filter((item) => can(role, item.permission));
  const lastRuns = useAsync(() => tracksApi.lastRuns(), []);

  const pullAt = lastRuns.data?.pull?.pulled_at ?? null;
  const normalizeAt = lastRuns.data?.normalize?.computed_at ?? null;

  return (
    <div className="shell">
      <aside className="rail">
        <div className="rail-mark">
          {BRAND.name}
          <small>{BRAND.tagline}</small>
        </div>
        <nav className="rail-nav">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) => `rail-link${isActive ? ' active' : ''}`}
            >
              <span>{item.label}</span>
              <span className="k">{item.hint}</span>
            </NavLink>
          ))}
        </nav>
        <div className="radar" aria-hidden="true">
          <div className="radar-sweep" />
          <span className="radar-blip" style={{ left: '63%', top: '29%' }} />
          <span className="radar-blip" style={{ left: '38%', top: '62%' }} />
          <span className="radar-blip" style={{ left: '72%', top: '70%' }} />
        </div>
        <div className="rail-foot">
          <div className="rail-user">
            {state.user?.display_name ?? '未登录'}
            <small>{state.user ? ROLE_LABEL[state.user.role] : ''}</small>
          </div>
          <button
            className="link-btn"
            onClick={() => {
              authStore.logout();
              navigate('/login');
            }}
          >
            退出登录
          </button>
        </div>
      </aside>
      <main className="main">
        <div className="topline">
          <div className="topline-group">
            <span>
              SYS · <strong>TRACKNORM</strong> DISPATCH CONSOLE
            </span>
            <span>承运商 3 · 归一状态 8</span>
          </div>
          <div className="topline-group">
            <span>
              最后拉取 <strong>{pullAt ? fmtTime(pullAt) : '—'}</strong>
            </span>
            <span>
              最后归一 <strong>{normalizeAt ? fmtTime(normalizeAt) : '—'}</strong>
            </span>
            <span>{state.user?.email}</span>
          </div>
        </div>
        {children}
      </main>
      <Toasts />
    </div>
  );
}
