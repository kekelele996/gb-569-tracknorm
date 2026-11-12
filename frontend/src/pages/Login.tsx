import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { authApi } from '../api/auth';
import { authStore } from '../stores/authStore';
import { errorMessage } from '../utils/errorMessage';

const DEMO_ACCOUNTS = [
  { email: 'admin@tracknorm.io', label: '运营主管', hint: '映射/承运商/预警' },
  { email: 'ops@tracknorm.io', label: '客服专员', hint: '拉取/归一/处置' },
  { email: 'client@tracknorm.io', label: '商家只读', hint: '只看自己的单' },
];

export default function Login() {
  const navigate = useNavigate();
  const [email, setEmail] = useState('admin@tracknorm.io');
  const [password, setPassword] = useState('Demo@2026');
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      const result = await authApi.login(email, password);
      authStore.setSession(result.access_token, result.user);
      navigate('/waybills', { replace: true });
    } catch (err) {
      const payload = (err as { payload?: unknown }).payload;
      setError(errorMessage(payload, '登录失败'));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="login">
      <section className="login-brand">
        <div>
          <div className="login-mark">
            tracknorm<span>.</span>
          </div>
          <p className="login-tag">
            迅联供应链 · 客户服务部 · 3 家承运商 2000 单轨迹聚合：把「已揽收 / COLLECTED /
            PICKUP_DONE」翻成自家 8 个状态，先把停半路的大件单捞出来。
          </p>
        </div>
        <div>
          <p className="login-quote">
            状态码可以乱，
            <br />
            但客户的<em>投诉不能先到</em>。
          </p>
          <div className="login-stats">
            <div className="login-stat">
              <strong>200</strong>
              <span>演示运单</span>
            </div>
            <div className="login-stat">
              <strong>8</strong>
              <span>归一状态</span>
            </div>
            <div className="login-stat">
              <strong>97.5%</strong>
              <span>映射覆盖率</span>
            </div>
            <div className="login-stat">
              <strong>6</strong>
              <span>停滞预警</span>
            </div>
          </div>
        </div>
        <div className="login-scan" aria-hidden="true">
          <div className="radar">
            <div className="radar-sweep" />
            <span className="radar-blip" style={{ left: '58%', top: '34%' }} />
            <span className="radar-blip" style={{ left: '34%', top: '58%' }} />
          </div>
        </div>
      </section>
      <section className="login-panel">
        <form className="login-card" onSubmit={submit}>
          <div className="eyebrow">DISPATCH CONSOLE · 登录</div>
          <h1>接管调度台</h1>
          <p className="sub">映射规则、停滞预警与承运商配额都在这块屏前处理。</p>
          <label className="field">
            <span>邮箱</span>
            <input
              className="input"
              type="email"
              value={email}
              autoComplete="username"
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label className="field">
            <span>密码</span>
            <input
              className="input"
              type="password"
              value={password}
              autoComplete="current-password"
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button className="btn btn-primary" style={{ width: '100%' }} type="submit" disabled={busy}>
            {busy ? '校验中 …' : '进入调度台'}
          </button>
          {error ? <div className="form-error">{error}</div> : null}
          <div className="hint-accounts">
            <span>演示账号（Demo@2026）：</span>
            {DEMO_ACCOUNTS.map((account) => (
              <button
                key={account.email}
                type="button"
                title={account.hint}
                onClick={() => {
                  setEmail(account.email);
                  setPassword('Demo@2026');
                }}
              >
                {account.label}
              </button>
            ))}
          </div>
        </form>
      </section>
    </div>
  );
}
