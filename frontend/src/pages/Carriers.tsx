import { useState } from 'react';
import { useSyncExternalStore } from 'react';
import { carriersApi } from '../api/carriers';
import { reportsApi } from '../api/reports';
import { tracksApi } from '../api/tracks';
import { useAsync } from '../hooks/useAsync';
import { authStore } from '../stores/authStore';
import { can } from '../constants/roles';
import type { Role } from '../types/models';
import RunPanel from '../components/common/RunPanel';
import MetricTile from '../components/common/MetricTile';
import EmptyState from '../components/common/EmptyState';
import { fmtDateTime, fmtPercent } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import { uiStore } from '../stores/uiStore';

export default function Carriers() {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const role = state.user?.role as Role | undefined;
  const canWrite = can(role, 'carrier:write');

  const carriers = useAsync(() => carriersApi.list(), []);
  const quality = useAsync(() => reportsApi.quality(), []);
  const pullLogs = useAsync(() => reportsApi.pullLogs(6), []);
  const [editing, setEditing] = useState<Record<number, { quota: string; rate: string }>>({});
  const [busyId, setBusyId] = useState<number | null>(null);

  function editValue(item: { id: number; daily_quota: number; rate_limit_per_min: number }) {
    return editing[item.id] ?? { quota: String(item.daily_quota), rate: String(item.rate_limit_per_min) };
  }

  async function save(item: { id: number; daily_quota: number; rate_limit_per_min: number }) {
    const value = editValue(item);
    setBusyId(item.id);
    try {
      await carriersApi.update(item.id, {
        daily_quota: Number(value.quota),
        rate_limit_per_min: Number(value.rate),
      });
      uiStore.push(`已更新 ${item.id} 号承运商配额/频率`);
      carriers.reload();
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '更新失败'), 'error');
    } finally {
      setBusyId(null);
    }
  }

  async function exportCsv() {
    try {
      const rows = await reportsApi.exportDelayNotices();
      uiStore.push(`已导出延迟说明 CSV（${rows} 行）`);
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '导出失败'), 'error');
    }
  }

  const qualityRows = quality.data?.items ?? [];

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">CARRIER OPS · 承运商与质量</div>
          <h1 className="page-title">承运商配置 · 数据质量</h1>
          <p className="page-sub">
            3 家承运商的码表、配额与频率；拉取统计里的 429 命中、归一后的重复/乱序/冲突决定质量分。
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-small" onClick={exportCsv}>
            导出延迟说明 CSV
          </button>
        </div>
      </header>

      <RunPanel
        canRun={can(role, 'track:pull')}
        onPull={() => tracksApi.pull()}
        onNormalize={async () => {
          const result = await tracksApi.normalize();
          quality.reload();
          return result;
        }}
      />

      <div className="grid grid-3">
        {(carriers.data?.items ?? []).map((item) => {
          const value = editValue(item);
          return (
            <section className="panel" key={item.id}>
              <div className="panel-head">
                <span className="panel-title">{item.code}</span>
                <span className={`badge${item.is_active ? ' badge-exact' : ' badge-danger'}`}>
                  {item.is_active ? '启用中' : '已停用'}
                </span>
              </div>
              <div className="panel-body" style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
                <div>
                  <h3 style={{ fontSize: '1.05rem' }}>{item.name}</h3>
                  <p className="soft" style={{ fontSize: '0.76rem' }}>
                    {item.status_code_system}
                  </p>
                </div>
                <div className="metric-grid">
                  <MetricTile label="运单" value={item.waybill_count} />
                  <MetricTile label="429 命中" value={Number(item.last_pull_stats?.rate_limit_hits ?? 0)} hint="最近拉取" />
                  <MetricTile label="最后拉取" value={fmtDateTime(item.last_pull_at)} />
                </div>
                {canWrite ? (
                  <div className="toolbar">
                    <label className="field" style={{ flex: 1 }}>
                      <span>日配额</span>
                      <input
                        className="input"
                        value={value.quota}
                        onChange={(event) =>
                          setEditing((current) => ({
                            ...current,
                            [item.id]: { ...value, quota: event.target.value },
                          }))
                        }
                      />
                    </label>
                    <label className="field" style={{ flex: 1 }}>
                      <span>每分钟</span>
                      <input
                        className="input"
                        value={value.rate}
                        onChange={(event) =>
                          setEditing((current) => ({
                            ...current,
                            [item.id]: { ...value, rate: event.target.value },
                          }))
                        }
                      />
                    </label>
                    <button
                      className="btn btn-small"
                      style={{ alignSelf: 'flex-end' }}
                      disabled={busyId === item.id}
                      onClick={() => save(item)}
                    >
                      保存
                    </button>
                  </div>
                ) : (
                  <dl className="kv-table">
                    <dt>日配额</dt>
                    <dd>{item.daily_quota}</dd>
                    <dt>每分钟</dt>
                    <dd>{item.rate_limit_per_min}</dd>
                  </dl>
                )}
                <p className="muted" style={{ fontSize: '0.72rem' }}>{item.note ?? '—'}</p>
              </div>
            </section>
          );
        })}
      </div>

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">数据质量报表 · 归一后统计</span>
          <span className="mono muted" style={{ fontSize: '0.68rem' }}>
            质量分 = 覆盖率×0.5 + (1−重复率)×0.2 + (1−冲突率)×0.3
          </span>
        </div>
        <div className="table-wrap">
          {quality.loading ? <p className="loading-line" style={{ padding: '1rem' }}>正在汇总 …</p> : null}
          {quality.error ? (
            <div className="error-state">
              <span>{errorMessage((quality.error as { payload?: unknown } | null)?.payload, '质量报表加载失败')}</span>
              <button className="btn btn-small" onClick={quality.reload}>重试</button>
            </div>
          ) : null}
          {!quality.loading && !quality.error && qualityRows.length === 0 ? (
            <EmptyState title="还没有质量数据" detail="先跑一次拉取与归一，报表会按承运商汇总。" />
          ) : null}
          {qualityRows.length > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>承运商</th>
                  <th>运单 / 事件</th>
                  <th>覆盖率</th>
                  <th>重复回推</th>
                  <th>乱序</th>
                  <th>非法回退</th>
                  <th>未命中码</th>
                  <th>质量分</th>
                </tr>
              </thead>
              <tbody>
                {qualityRows.map((row) => (
                  <tr key={row.carrier_id} style={{ cursor: 'default' }}>
                    <td>
                      {row.carrier_name}
                      <span className="cell-sub mono">{row.carrier_code}</span>
                    </td>
                    <td className="mono">
                      {row.waybills} / {row.events}
                    </td>
                    <td>
                      <div className="coverage">
                        <div className={`coverage-bar${row.coverage < 0.95 ? ' low' : ''}`}>
                          <span style={{ width: `${Math.round(row.coverage * 100)}%` }} />
                        </div>
                        <span className="mono" style={{ fontSize: '0.72rem' }}>{fmtPercent(row.coverage, 1)}</span>
                      </div>
                    </td>
                    <td className="mono">{row.duplicate_events}</td>
                    <td className="mono">{row.disorder_events}</td>
                    <td className="mono">{row.conflict_events}</td>
                    <td className="mono">{row.unmapped_events}</td>
                    <td>
                      <div className="coverage">
                        <div className="coverage-bar">
                          <span style={{ width: `${Math.round(row.quality_score * 100)}%` }} />
                        </div>
                        <span className="mono" style={{ fontSize: '0.72rem' }}>{row.quality_score.toFixed(3)}</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
      </section>

      {can(role, 'report:audit') ? (
        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">最近跑批审计</span>
            <span className="mono muted" style={{ fontSize: '0.68rem' }}>HTTP 写请求 + 领域动作双层</span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>时间</th>
                  <th>操作</th>
                  <th>操作人</th>
                  <th>对象</th>
                  <th>摘要</th>
                </tr>
              </thead>
              <tbody>
                {(pullLogs.data?.items ?? []).map((log) => (
                  <tr key={log.id} style={{ cursor: 'default' }}>
                    <td className="mono">{fmtDateTime(log.created_at)}</td>
                    <td>{log.action_label}</td>
                    <td className="mono">{log.actor_email}</td>
                    <td className="mono">{log.entity}</td>
                    <td className="soft" style={{ fontSize: '0.74rem' }}>
                      {JSON.stringify(log.detail).slice(0, 110)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      ) : null}
    </div>
  );
}
