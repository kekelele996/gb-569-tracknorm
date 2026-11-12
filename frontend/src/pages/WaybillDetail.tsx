import { useNavigate, useParams } from 'react-router-dom';
import { waybillsApi } from '../api/waybills';
import { reportsApi } from '../api/reports';
import { useAsync } from '../hooks/useAsync';
import StatusLamp from '../components/common/StatusLamp';
import TrackTimeline from '../components/common/TrackTimeline';
import MetricTile from '../components/common/MetricTile';
import ScoreBadge from '../components/common/ScoreBadge';
import { fmtDateTime, fmtPercent } from '../utils/format';
import { STATUS_LABEL } from '../constants/enums';
import { errorMessage } from '../utils/errorMessage';
import { uiStore } from '../stores/uiStore';

export default function WaybillDetail() {
  const { waybillId } = useParams();
  const navigate = useNavigate();
  const id = Number(waybillId);
  const detail = useAsync(() => waybillsApi.detail(id), [id]);

  const data = detail.data;

  async function exportCsv() {
    try {
      const rows = await reportsApi.exportDelayNotices();
      uiStore.push(`已导出延迟说明 CSV（${rows} 行）`);
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '导出失败'), 'error');
    }
  }

  if (detail.loading) {
    return <p className="loading-line" style={{ padding: '2rem' }}>正在载入轨迹 …</p>;
  }
  if (detail.error || !data) {
    return (
      <div className="page">
        <div className="error-state">
          <span>{errorMessage((detail.error as { payload?: unknown } | null)?.payload, '运单加载失败')}</span>
          <button className="btn btn-small" onClick={detail.reload}>重试</button>
        </div>
      </div>
    );
  }

  const waybill = data.waybill;
  const conflicts = data.conflicts;

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <button className="link-btn" onClick={() => navigate('/waybills')} style={{ marginBottom: '0.5rem' }}>
            ← 返回运单总览
          </button>
          <div className="eyebrow">
            {waybill.carrier_name} · {waybill.lane} · {waybill.service_level_label}
          </div>
          <h1 className="page-title mono" style={{ fontSize: 'clamp(1.4rem, 2vw, 1.9rem)' }}>
            {waybill.waybill_no}
          </h1>
          <p className="page-sub">
            商家单号 {waybill.client_ref} · 归属 {waybill.client_account} · 原始最新阶段{' '}
            {STATUS_LABEL[waybill.trace_stage] ?? waybill.trace_stage}（归一为{' '}
            {STATUS_LABEL[waybill.current_status] ?? waybill.current_status}）
          </p>
        </div>
        <div className="page-actions">
          {data.alert_id ? (
            <button className="btn btn-small" onClick={() => navigate('/alerts')}>
              查看停滞预警 · {data.alert_severity}
            </button>
          ) : null}
          <button className="btn btn-small" onClick={exportCsv}>
            导出延迟说明 CSV
          </button>
        </div>
      </header>

      <div className="metric-grid">
        <MetricTile label="当前状态" value={<StatusLamp status={waybill.current_status} />} hint="算法 1 输出" accent />
        <MetricTile label="映射覆盖率" value={fmtPercent(data.coverage, 1)} hint={`v${data.mapping_version ?? '—'}`} />
        <MetricTile label="非法回退" value={conflicts.length} hint="状态机校验" />
        <MetricTile label="重复回推" value={data.duplicate_count} hint="30 分钟窗口" />
        <MetricTile label="乱序事件" value={data.disorder_count} hint="按 seq 到达序" />
        <MetricTile label="未命中码" value={data.unmapped_count} hint="映射 < 0.5" />
        <MetricTile label="承诺送达" value={fmtDateTime(waybill.promised_delivery_at)} />
        <MetricTile label="最后事件" value={fmtDateTime(waybill.last_event_at)} />
      </div>

      {conflicts.length > 0 ? (
        <div className="conflict-panel">
          <strong>检测到 {conflicts.length} 条非法回退（已保留前序状态，不计入归一轨迹）</strong>
          {conflicts.map((conflict) => (
            <div className="conflict-item" key={conflict.carrier_event_id}>
              <span className="mono">{conflict.raw_status}</span> · {fmtDateTime(conflict.event_time)} ·{' '}
              {conflict.location}：{STATUS_LABEL[conflict.from_status] ?? conflict.from_status} →{' '}
              {STATUS_LABEL[conflict.to_status] ?? conflict.to_status}（{conflict.reason_label}）
            </div>
          ))}
        </div>
      ) : null}

      <div className="grid grid-2">
        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">原始事件 · 承运商到达顺序（{data.events.length}）</span>
            <span className="mono muted" style={{ fontSize: '0.68rem' }}>未经翻译，seq 为承运商序号</span>
          </div>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr>
                  <th>seq</th>
                  <th>原始状态码</th>
                  <th>事件时间</th>
                  <th>地点</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((event) => (
                  <tr key={event.id} style={{ cursor: 'default' }}>
                    <td className="mono">{String(event.seq).padStart(2, '0')}</td>
                    <td className="mono">{event.raw_status}</td>
                    <td className="mono">{fmtDateTime(event.event_time)}</td>
                    <td>{event.location}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="panel">
          <div className="panel-head">
            <span className="panel-title">归一轨迹 · 时间轴（{data.normalized_events.length}）</span>
            <span className="mono muted" style={{ fontSize: '0.68rem' }}>排序 + 去重 + 状态机后</span>
          </div>
          <div className="panel-body">
            <TrackTimeline events={data.normalized_events} />
          </div>
        </section>
      </div>

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">映射命中明细</span>
          <span className="mono muted" style={{ fontSize: '0.68rem' }}>精确 1.0 / 别名 0.8 / 模糊 0.5–0.7</span>
        </div>
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>命中码</th>
                <th>归一状态</th>
                <th>匹配方式</th>
                <th>命中次数</th>
                <th>引发冲突</th>
              </tr>
            </thead>
            <tbody>
              {data.mapping_hits.map((hit) => (
                <tr key={`${hit.rule_id}-${hit.source_status}`} style={{ cursor: 'default' }}>
                  <td className="mono">{hit.source_status}</td>
                  <td>
                    <StatusLamp status={hit.target_status} />
                  </td>
                  <td>
                    <ScoreBadge matchType={hit.match_type} score={hit.score} />
                  </td>
                  <td className="mono">{hit.hits}</td>
                  <td>
                    {hit.conflicts ? <span className="badge badge-danger">{hit.conflicts}</span> : <span className="muted">—</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
