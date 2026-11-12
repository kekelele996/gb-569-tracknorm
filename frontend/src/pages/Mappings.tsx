import { useEffect, useState } from 'react';
import { useSyncExternalStore } from 'react';
import { Link } from 'react-router-dom';
import { mappingsApi } from '../api/mappings';
import { useAsync } from '../hooks/useAsync';
import { authStore } from '../stores/authStore';
import { can } from '../constants/roles';
import type { Role } from '../types/models';
import MetricTile from '../components/common/MetricTile';
import StatusLamp from '../components/common/StatusLamp';
import ScoreBadge from '../components/common/ScoreBadge';
import EmptyState from '../components/common/EmptyState';
import { fmtPercent, fmtDateTime } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import { uiStore } from '../stores/uiStore';

export default function Mappings() {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const role = state.user?.role as Role | undefined;
  const canWrite = can(role, 'mapping:write');
  const versions = useAsync(() => mappingsApi.versions(), []);
  const [version, setVersion] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (version === null && versions.data?.active_version) {
      setVersion(versions.data.active_version);
    }
  }, [versions.data, version]);

  const rules = useAsync(() => mappingsApi.rules(version ?? undefined), [version]);
  const stats = useAsync(() => mappingsApi.evaluate(version ?? undefined), [version]);

  async function createVersion() {
    if (!version) return;
    setBusy(true);
    try {
      const created = await mappingsApi.createVersion(version);
      uiStore.push(`已创建 v${created.version}（继承 ${created.copied_rules} 条 + 新增 ${created.added_rules} 条别名规则）`);
      versions.reload();
      setVersion(created.version);
      rules.reload();
      stats.reload();
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '创建版本失败'), 'error');
    } finally {
      setBusy(false);
    }
  }

  async function activate() {
    if (!version) return;
    setBusy(true);
    try {
      const active = await mappingsApi.activate(version);
      uiStore.push(`已启用 v${active.version}（${active.rules} 条规则），可到运单页重算归一`);
      versions.reload();
      stats.reload();
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '启用版本失败'), 'error');
    } finally {
      setBusy(false);
    }
  }

  const totalConflicts = stats.data?.conflicts ?? 0;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">CODEBOOK · 映射规则</div>
          <h1 className="page-title">状态码表版本</h1>
          <p className="page-sub">
            3 家承运商码表 → 自家 8 个状态。按版本管理规则与置信分；版本切换后重算归一，冲突条数会立刻变化。
          </p>
        </div>
        <div className="page-actions">
          {canWrite ? (
            <>
              <button className="btn btn-small" disabled={busy || !version} onClick={createVersion}>
                以 v{version ?? '—'} 为基线生成新版本
              </button>
              <button className="btn btn-small btn-primary" disabled={busy || !version} onClick={activate}>
                启用 v{version ?? '—'}
              </button>
            </>
          ) : (
            <span className="chip">只读 · 仅运营主管可发布版本</span>
          )}
        </div>
      </header>

      <div className="toolbar">
        {(versions.data?.versions ?? []).map((item) => (
          <button
            key={item.version}
            className={`chip${version === item.version ? ' active' : ''}`}
            onClick={() => setVersion(item.version)}
          >
            v{item.version} · {item.rules} 条{item.is_active ? ' · 启用中' : ''}
          </button>
        ))}
        {versions.data ? (
          <span className="mono muted" style={{ fontSize: '0.68rem' }}>
            当前启用版本 v{versions.data.active_version}
          </span>
        ) : null}
      </div>

      <div className="metric-grid">
        <MetricTile label="覆盖率" value={stats.data ? `${stats.data.coverage_percent}` : '—'} unit="%" hint="命中映射事件 / 原始事件" accent />
        <MetricTile label="非法回退冲突" value={totalConflicts} hint="状态机判定" />
        <MetricTile label="未命中事件" value={stats.data?.unmapped_events ?? '—'} hint="候选分 < 0.5" />
        <MetricTile label="事件总数" value={stats.data?.events ?? '—'} />
        <MetricTile label="重算耗时" value={((stats.data?.duration_ms ?? 0) / 1000).toFixed(2)} unit="s" hint="内存重算，不落库" />
      </div>

      {stats.data ? (
        <div className="toolbar">
          {stats.data.by_status.map((bucket) => (
            <span className="chip" key={bucket.status}>
              <StatusLamp status={bucket.status} />
              <span className="mono">{bucket.count}</span>
            </span>
          ))}
        </div>
      ) : null}

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">规则表 · v{version ?? '—'}</span>
          <span className="mono muted" style={{ fontSize: '0.68rem' }}>
            模糊规则由人工标定置信分（0.5–0.7），精确/别名按固定分
          </span>
        </div>
        <div className="table-wrap">
          {rules.loading ? <p className="loading-line" style={{ padding: '1rem' }}>正在读取规则 …</p> : null}
          {rules.error ? (
            <div className="error-state">
              <span>{errorMessage((rules.error as { payload?: unknown } | null)?.payload, '规则加载失败')}</span>
              <button className="btn btn-small" onClick={rules.reload}>重试</button>
            </div>
          ) : null}
          {!rules.error && (rules.data?.rules.length ?? 0) === 0 ? (
            <EmptyState title="该版本还没有规则" detail="以 v1 为基线生成新版本后再查看。" />
          ) : null}
          {!rules.error && (rules.data?.rules.length ?? 0) > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>承运商</th>
                  <th>承运商码</th>
                  <th>归一状态</th>
                  <th>匹配方式</th>
                  <th>命中</th>
                  <th>冲突</th>
                  <th>说明</th>
                </tr>
              </thead>
              <tbody>
                {(rules.data?.rules ?? []).map((rule) => (
                  <tr key={rule.id} style={{ cursor: 'default' }}>
                    <td className="mono">{rule.carrier_code}</td>
                    <td className="mono">{rule.source_status}</td>
                    <td>
                      <StatusLamp status={rule.target_status} />
                    </td>
                    <td>
                      <ScoreBadge matchType={rule.match_type} score={rule.score} />
                    </td>
                    <td className="mono">{rule.hits}</td>
                    <td>
                      {rule.conflicts ? <span className="badge badge-danger">{rule.conflicts}</span> : <span className="muted">—</span>}
                    </td>
                    <td className="soft" style={{ fontSize: '0.76rem', maxWidth: 300 }}>
                      {rule.note ?? '—'}
                      <span className="cell-sub mono">{fmtDateTime(rule.created_at)}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      </section>

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">冲突清单 · v{version ?? '—'}（{totalConflicts} 条）</span>
          <span className="mono muted" style={{ fontSize: '0.68rem' }}>回退事件不改变当前状态，需在规则或承运商侧修正</span>
        </div>
        <div className="table-wrap">
          {totalConflicts === 0 ? (
            <EmptyState title="该版本无非法回退冲突" detail="状态机校验全部通过。" />
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>运单</th>
                  <th>承运商</th>
                  <th>回退码</th>
                  <th>迁移</th>
                  <th>事件时间</th>
                  <th>原因</th>
                </tr>
              </thead>
              <tbody>
                {(stats.data?.conflict_items ?? []).map((item) => (
                  <tr key={`${item.waybill_id}-${item.event_time}-${item.raw_status}`}>
                    <td className="mono">
                      <Link to={`/waybills/${item.waybill_id}`} className="mono">
                        {item.waybill_no}
                      </Link>
                    </td>
                    <td className="mono">{item.carrier_code}</td>
                    <td className="mono">{item.raw_status}</td>
                    <td>
                      <StatusLamp status={item.from_status} />
                      <span className="muted"> → </span>
                      <StatusLamp status={item.to_status} />
                    </td>
                    <td className="mono">{fmtDateTime(item.event_time)}</td>
                    <td>{item.reason_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </section>

      {stats.data ? (
        <p className="mono muted" style={{ fontSize: '0.68rem' }}>
          v{stats.data.version} 内存重算：覆盖率 {fmtPercent(stats.data.coverage, 1)} · 事件 {stats.data.events} · 冲突{' '}
          {stats.data.conflicts} · 耗时 {stats.data.duration_ms} ms（不落库，用于版本对比）
        </p>
      ) : null}
    </div>
  );
}
