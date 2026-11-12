import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useSyncExternalStore } from 'react';
import { authStore } from '../stores/authStore';
import { can } from '../constants/roles';
import type { Role } from '../types/models';
import { waybillsApi } from '../api/waybills';
import { tracksApi } from '../api/tracks';
import { reportsApi } from '../api/reports';
import { useAsync } from '../hooks/useAsync';
import { useDebounce } from '../hooks/useDebounce';
import StatusLamp from '../components/common/StatusLamp';
import RunPanel from '../components/common/RunPanel';
import EmptyState from '../components/common/EmptyState';
import { fmtDateTime, fmtPercent } from '../utils/format';
import { uiStore } from '../stores/uiStore';
import { errorMessage } from '../utils/errorMessage';

const PAGE_SIZE = 20;

export default function Waybills() {
  const state = useSyncExternalStore(authStore.subscribe, authStore.getState);
  const role = state.user?.role as Role | undefined;
  const isClient = role === 'client';
  const navigate = useNavigate();
  const [status, setStatus] = useState<string>('');
  const [carrier, setCarrier] = useState<string>('');
  const [query, setQuery] = useState('');
  const debounced = useDebounce(query);
  const [page, setPage] = useState(1);

  const list = useAsync(
    () => waybillsApi.list({ status, carrier_code: carrier, q: debounced, page, size: PAGE_SIZE }),
    [status, carrier, debounced, page],
  );
  const lastRuns = useAsync(() => tracksApi.lastRuns(), []);

  async function exportCsv() {
    try {
      const rows = await reportsApi.exportDelayNotices();
      uiStore.push(`已导出延迟说明 CSV（${rows} 行）`);
    } catch (err) {
      uiStore.push(errorMessage((err as { payload?: unknown }).payload, '导出失败'), 'error');
    }
  }

  const buckets = list.data?.buckets ?? [];
  const carrierOptions = list.data?.carriers ?? [];
  const total = list.data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="page">
      <header className="page-head">
        <div>
          <div className="eyebrow">MANIFEST · 运单总览</div>
          <h1 className="page-title">{isClient ? '我的运单' : '运单总览'}</h1>
          <p className="page-sub">
            {isClient
              ? '只展示 client@tracknorm.io 名下运单；状态、轨迹与映射命中均来自后端归一结果。'
              : '200 单按自家 8 个状态分桶，原始承运商码表在这里被翻译成一套口径；点击行看「原始事件 vs 归一轨迹」。'}
          </p>
        </div>
        <div className="page-actions">
          {!isClient ? (
            <button className="btn btn-small" onClick={exportCsv}>
              导出延迟说明 CSV
            </button>
          ) : (
            <button className="btn btn-small" onClick={exportCsv}>
              导出我的延迟说明
            </button>
          )}
          <button className="btn btn-small" onClick={() => { list.reload(); lastRuns.reload(); }}>
            刷新
          </button>
        </div>
      </header>

      {!isClient ? (
        <RunPanel
          canRun={can(role, 'track:pull')}
          onPull={() => tracksApi.pull()}
          onNormalize={async () => {
            const result = await tracksApi.normalize();
            list.reload();
            return result;
          }}
        />
      ) : null}

      <div className="bucket-strip">
        {buckets.map((bucket) => (
          <button
            key={bucket.status}
            className={`bucket${status === bucket.status ? ' active' : ''}`}
            onClick={() => {
              setStatus(status === bucket.status ? '' : bucket.status);
              setPage(1);
            }}
          >
            <span className="bucket-top">
              <StatusLamp status={bucket.status} />
            </span>
            <span className="bucket-count">{bucket.count}</span>
          </button>
        ))}
      </div>

      <section className="panel">
        <div className="panel-head">
          <span className="panel-title">筛选</span>
          <span className="mono muted" style={{ fontSize: '0.7rem' }}>
            共 {total} 单{status ? ` · 状态 ${status}` : ''}
          </span>
        </div>
        <div className="panel-body toolbar">
          <div className="toolbar-group">
            <input
              className="input"
              style={{ width: 230 }}
              placeholder="运单号 / 商家单号 / 城市"
              value={query}
              onChange={(event) => {
                setQuery(event.target.value);
                setPage(1);
              }}
            />
          </div>
          <div className="toolbar-group">
            {carrierOptions.map((item) => (
              <button
                key={item.code}
                className={`chip${carrier === item.code ? ' active' : ''}`}
                onClick={() => {
                  setCarrier(carrier === item.code ? '' : item.code);
                  setPage(1);
                }}
              >
                {item.name}
              </button>
            ))}
            {status ? (
              <button
                className="chip"
                onClick={() => {
                  setStatus('');
                  setPage(1);
                }}
              >
                清除状态
              </button>
            ) : null}
          </div>
        </div>
        <div className="table-wrap">
          {list.loading ? <p className="loading-line" style={{ padding: '1rem' }}>正在读取运单 …</p> : null}
          {list.error ? (
            <div className="error-state">
              <span>{errorMessage((list.error as { payload?: unknown } | null)?.payload, '运单列表加载失败')}</span>
              <button className="btn btn-small" onClick={list.reload}>
                重试
              </button>
            </div>
          ) : null}
          {!list.loading && !list.error && (list.data?.items.length ?? 0) === 0 ? (
            <EmptyState
              title="没有符合条件的运单"
              detail="换个状态分桶或清空搜索词；也可以先在上方「跑批操作台」拉取一次承运商轨迹。"
              action={
                <button
                  className="btn btn-small"
                  onClick={() => {
                    setStatus('');
                    setCarrier('');
                    setQuery('');
                    list.reload();
                  }}
                >
                  清空筛选
                </button>
              }
            />
          ) : null}
          {!list.error && (list.data?.items.length ?? 0) > 0 ? (
            <table className="data-table">
              <thead>
                <tr>
                  <th>运单 / 商家单号</th>
                  <th>承运商</th>
                  <th>线路</th>
                  <th>当前状态</th>
                  <th>承诺送达</th>
                  <th>最后事件</th>
                  <th>覆盖率</th>
                  <th>冲突</th>
                </tr>
              </thead>
              <tbody>
                {(list.data?.items ?? []).map((item) => (
                  <tr key={item.id} onClick={() => navigate(`/waybills/${item.id}`)}>
                    <td>
                      <span className="wb-no">{item.waybill_no}</span>
                      <span className="cell-sub mono">{item.client_ref}</span>
                    </td>
                    <td>
                      {item.carrier_name}
                      <span className="cell-sub mono">{item.carrier_code}</span>
                    </td>
                    <td className="mono">{item.lane}</td>
                    <td>
                      <StatusLamp status={item.current_status} />
                    </td>
                    <td className="mono">{fmtDateTime(item.promised_delivery_at)}</td>
                    <td className="mono">{fmtDateTime(item.last_event_at)}</td>
                    <td>
                      <div className="coverage">
                        <div className={`coverage-bar${item.coverage < 0.9 ? ' low' : ''}`}>
                          <span style={{ width: `${Math.round(item.coverage * 100)}%` }} />
                        </div>
                        <span className="mono" style={{ fontSize: '0.72rem' }}>
                          {fmtPercent(item.coverage, 0)}
                        </span>
                      </div>
                    </td>
                    <td>
                      {item.conflict_count > 0 ? (
                        <span className="badge badge-danger">{item.conflict_count} 条回退</span>
                      ) : (
                        <span className="mono muted" style={{ fontSize: '0.72rem' }}>—</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : null}
        </div>
        <div className="pagination">
          <span>
            第 {page} / {totalPages} 页 · 每页 {PAGE_SIZE}
          </span>
          <div className="toolbar-group">
            <button
              className="btn btn-small"
              disabled={page <= 1}
              onClick={() => setPage((value) => Math.max(1, value - 1))}
            >
              上一页
            </button>
            <button
              className="btn btn-small"
              disabled={page >= totalPages}
              onClick={() => setPage((value) => Math.min(totalPages, value + 1))}
            >
              下一页
            </button>
          </div>
        </div>
      </section>

      {lastRuns.data?.normalize ? (
        <p className="mono muted" style={{ fontSize: '0.68rem' }}>
          最近归一 v{lastRuns.data.normalize.version} · 覆盖率 {lastRuns.data.normalize.coverage_percent}% ·
          冲突 {lastRuns.data.normalize.conflicts} 条 · 去重 {lastRuns.data.normalize.duplicates} 条 ·
          未命中 {lastRuns.data.normalize.unmapped_events} 条
        </p>
      ) : null}
    </div>
  );
}
