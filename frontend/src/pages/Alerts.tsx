import { useState } from 'react';
import { useSyncExternalStore } from 'react';
import { useNavigate } from 'react-router-dom';
import { alertsApi } from '../api/alerts';
import { tracksApi } from '../api/tracks';
import { useAsync } from '../hooks/useAsync';
import { authStore } from '../stores/authStore';
import { can } from '../constants/roles';
import type { Role } from '../types/models';
import MetricTile from '../components/common/MetricTile';
import StatusLamp from '../components/common/StatusLamp';
import TrackTimeline from '../components/common/TrackTimeline';
import EmptyState from '../components/common/EmptyState';
import { ALERT_SEVERITIES, ALERT_STATUSES, DISPOSITIONS, SEVERITY_LABEL, ALERT_STATUS_LABEL } from '../constants/enums';
import { fmtDateTime, fmtHours, fmtSignedHours } from '../utils/format';
import { errorMessage } from '../utils/errorMessage';
import { uiStore } from '../stores/uiStore';

export default function Alerts() {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const role = state.user?.role as Role | undefined;
  const canHandle = can(role, 'alert:handle');
  const navigate = useNavigate();

  const [severity, setSeverity] = useState('');
  const [status, setStatus] = useState('');
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [note, setNote] = useState('');
  const [disposition, setDisposition] = useState('contacting');
  const [busy, setBusy] = useState(false);

  const summary = useAsync(() => alertsApi.summary(), []);
  const list = useAsync(() => alertsApi.list({ severity, status }), [severity, status]);
  const lastRuns = useAsync(() => tracksApi.lastRuns(), []);
  const items = list.data?.items ?? [];
  const selected = items.find((item) => item.id === selectedId) ?? items[0] ?? null;
  const insufficient = Number(
    (lastRuns.data?.normalize?.stagnation as { insufficient_baseline?: number } | undefined)?.insufficient_baseline ?? 0,
  );

  async function claim() {
    if (!selected) return;
    setBusy(true);
    try {
      await alertsApi.claim(selected.id, note || undefined);
      uiStore.push(`已认领预警 ${selected.waybill_no}`);
      setNote('');
      list.reload();
      summary.reload();
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '认领失败'), 'error');
    } finally {
      setBusy(false);
    }
  }

  async function dispose() {
    if (!selected) return;
    setBusy(true);
    try {
      await alertsApi.dispose(selected.id, disposition, note || undefined);
      uiStore.push(`已处置 ${selected.waybill_no} · ${DISPOSITIONS.find((item) => item.value === disposition)?.label ?? disposition}`);
      setNote('');
      list.reload();
      summary.reload();
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '处置失败'), 'error');
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">STAGNATION RADAR · 停滞预警</div>
          <h1 className="page-title">雷达屏 · 停滞预警</h1>
          <p className="page-sub">
            基线 = 已签收运单在同承运商 × 同线路 × 同阶段的停留 P50 + MAD；稳健 z ≥ 3.5 即进入雷达。
            认领后处置留痕会写进审计与延迟说明 CSV。
          </p>
        </div>
        <div className="page-actions">
          <button className="btn btn-small" onClick={() => { list.reload(); summary.reload(); lastRuns.reload(); }}>
            刷新雷达
          </button>
        </div>
      </header>

      <div className="metric-grid">
        <MetricTile label="预警总数" value={summary.data?.total ?? '—'} hint="按 waybill 去重" accent />
        <MetricTile label="严重 critical" value={summary.data?.by_severity.critical ?? 0} hint="z ≥ 8" />
        <MetricTile label="预警 alert" value={summary.data?.by_severity.alert ?? 0} hint="z 5–8" />
        <MetricTile label="关注 warn" value={summary.data?.by_severity.warn ?? 0} hint="z 3.5–5" />
        <MetricTile label="待认领" value={summary.data?.by_status.open ?? 0} hint="open" />
        <MetricTile label="已认领" value={summary.data?.by_status.claimed ?? 0} hint="claimed" />
        <MetricTile label="已处置" value={summary.data?.by_status.handled ?? 0} hint="handled" />
        <MetricTile label="基线不足跳过" value={insufficient} hint="样本 < 5 的线路" />
      </div>

      <div className="toolbar">
        <div className="toolbar-group">
          {ALERT_SEVERITIES.map((item) => (
            <button
              key={item.value}
              className={`chip${severity === item.value ? ' active' : ''}`}
              onClick={() => setSeverity(severity === item.value ? '' : item.value)}
            >
              {item.label} · {item.hint}
            </button>
          ))}
        </div>
        <div className="toolbar-group">
          {ALERT_STATUSES.map((item) => (
            <button
              key={item.value}
              className={`chip${status === item.value ? ' active' : ''}`}
              onClick={() => setStatus(status === item.value ? '' : item.value)}
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      <div className="alert-layout">
        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">预警队列（{items.length}）</span>
            <span className="mono muted" style={{ fontSize: '0.68rem' }}>点击行查看归一轨迹与处置</span>
          </div>
          {list.loading ? <p className="loading-line" style={{ padding: '1rem' }}>雷达扫描中 …</p> : null}
          {list.error ? (
            <div className="error-state">
              <span>{errorMessage((list.error as { payload?: unknown } | null)?.payload, '预警加载失败')}</span>
              <button className="btn btn-small" onClick={list.reload}>重试</button>
            </div>
          ) : null}
          {!list.loading && !list.error && items.length === 0 ? (
            <EmptyState title="雷达干净" detail="当前筛选下没有停滞预警；可清除筛选或重跑归一 + 停滞扫描。" />
          ) : null}
          {!list.error && items.length > 0 ? (
            <div>
              {items.map((alert) => (
                <div
                  key={alert.id}
                  className={`alert-row${selected?.id === alert.id ? ' selected' : ''}`}
                  onClick={() => setSelectedId(alert.id)}
                >
                  <span className={`sev sev-${alert.severity}`}>
                    <StatusLamp severity={alert.severity} />
                  </span>
                  <div className="alert-main">
                    <span className="wb">{alert.waybill_no}</span>
                    <span className="lane">
                      {alert.carrier_name} · {alert.lane_key} · {alert.stage_label}
                    </span>
                  </div>
                  <div className="alert-figure figure-optional">
                    <span>{fmtHours(alert.dwell_minutes)}</span>
                    <small>停留</small>
                  </div>
                  <div className="alert-figure">
                    <span>{alert.robust_z.toFixed(2)}</span>
                    <small>稳健 z</small>
                  </div>
                  <div className="alert-figure">
                    <span>{fmtSignedHours(alert.deviation_hours)}</span>
                    <small>偏差</small>
                  </div>
                  <div className="alert-figure figure-optional">
                    <span>{ALERT_STATUS_LABEL[alert.status] ?? alert.status}</span>
                    <small>{alert.claimed_by ? alert.claimed_by.split('@')[0] : '未认领'}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>

        {selected ? (
          <aside className="alert-detail">
            <div>
              <div className="eyebrow">ALERT #{selected.id}</div>
              <h2 className="mono" style={{ fontSize: '1.1rem' }}>{selected.waybill_no}</h2>
              <p className="soft" style={{ fontSize: '0.78rem' }}>
                {selected.carrier_name} · {selected.lane_key} · 当前阶段 {selected.stage_label} · 商家单号{' '}
                {selected.client_ref}
              </p>
            </div>

            <div className="metric-grid">
              <MetricTile label="停留" value={fmtHours(selected.dwell_minutes)} />
              <MetricTile label="阶段基线 P50" value={fmtHours(selected.baseline_p50_minutes)} />
              <MetricTile label="MAD" value={`${selected.baseline_mad_minutes.toFixed(1)}`} unit="min" />
              <MetricTile label="样本" value={selected.baseline_samples} hint="已签收单" />
              <MetricTile label="稳健 z" value={selected.robust_z.toFixed(2)} hint={SEVERITY_LABEL[selected.severity] ?? selected.severity} accent />
              <MetricTile label="预计偏差" value={fmtSignedHours(selected.deviation_hours)} hint="预计 − 承诺" />
            </div>

            <dl className="kv-table">
              <dt>承诺送达</dt>
              <dd>{fmtDateTime(selected.promised_delivery_at)}</dd>
              <dt>预计送达</dt>
              <dd>{fmtDateTime(selected.predicted_delivery_at)}</dd>
              <dt>检测时刻</dt>
              <dd>{fmtDateTime(selected.detected_at)}</dd>
              <dt>认领人</dt>
              <dd>{selected.claimed_by ?? '—'}</dd>
              <dt>处置动作</dt>
              <dd>{selected.disposition_label ?? '—'}</dd>
              <dt>处置说明</dt>
              <dd style={{ fontFamily: 'var(--font-sans)' }}>{selected.note ?? '—'}</dd>
            </dl>

            <div>
              <div className="panel-title" style={{ marginBottom: '0.5rem' }}>归一轨迹</div>
              <TrackTimeline events={selected.timeline} />
            </div>

            {canHandle ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                <label className="field">
                  <span>处置说明</span>
                  <textarea
                    className="textarea"
                    value={note}
                    placeholder="例如：已联系客户说明预计晚到 2 小时并补偿运费券"
                    onChange={(event) => setNote(event.target.value)}
                  />
                </label>
                <div className="alert-actions">
                  <button className="btn btn-small" disabled={busy || selected.status !== 'open'} onClick={claim}>
                    认领预警
                  </button>
                  <select
                    className="select"
                    style={{ width: 160 }}
                    value={disposition}
                    onChange={(event) => setDisposition(event.target.value)}
                  >
                    {DISPOSITIONS.map((item) => (
                      <option key={item.value} value={item.value}>
                        {item.label}
                      </option>
                    ))}
                  </select>
                  <button
                    className="btn btn-small btn-primary"
                    disabled={busy || ['handled', 'dismissed'].includes(selected.status)}
                    onClick={dispose}
                  >
                    处置并留痕
                  </button>
                </div>
                <button className="btn btn-small btn-ghost" onClick={() => navigate(`/waybills/${selected.waybill_id}`)}>
                  打开运单详情 →
                </button>
              </div>
            ) : (
              <span className="chip">当前角色只读预警（处置需客服/运营主管）</span>
            )}
          </aside>
        ) : null}
      </div>
    </div>
  );
}
