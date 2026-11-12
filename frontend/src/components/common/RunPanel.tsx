import { useState } from 'react';
import MetricTile from './MetricTile';

export interface RunResult {
  events_fetched?: number;
  events_inserted?: number;
  rate_limit_hits?: number;
  backoff_ms?: number[];
  coverage_percent?: number;
  conflicts?: number;
  duplicates?: number;
  unmapped_events?: number;
  duration_ms?: number;
  waybills?: number;
  version?: number;
}

interface Props {
  canRun: boolean;
  onPull: () => Promise<RunResult>;
  onNormalize: () => Promise<RunResult>;
}

/** 拉取 / 归一操作台（运单总览与承运商质量页共用）。 */
export default function RunPanel({ canRun, onPull, onNormalize }: Props) {
  const [busy, setBusy] = useState<'pull' | 'normalize' | null>(null);
  const [result, setResult] = useState<RunResult | null>(null);
  const [log, setLog] = useState<string[]>([]);
  const [error, setError] = useState('');

  function pushLog(line: string) {
    setLog((current) => [line, ...current].slice(0, 12));
  }

  async function run(kind: 'pull' | 'normalize') {
    setBusy(kind);
    setError('');
    try {
      const output = kind === 'pull' ? await onPull() : await onNormalize();
      setResult(output);
      if (kind === 'pull') {
        pushLog(
          `→ 拉取完成：${output.waybills ?? 0} 单 / ${output.events_fetched ?? 0} 事件，新写入 ${
            output.events_inserted ?? 0
          }，429 退避 ${output.rate_limit_hits ?? 0} 次`,
        );
        (output.backoff_ms ?? []).forEach((ms, index) => pushLog(`   · 429 退避 #${index + 1}: ${ms} ms → 重试成功`));
        pushLog(`   · 幂等校验：未变化 ${(output.events_fetched ?? 0) - (output.events_inserted ?? 0)} 条`);
      } else {
        pushLog(
          `→ 归一完成 v${output.version ?? '—'}：覆盖率 ${output.coverage_percent ?? '—'}%，冲突 ${
            output.conflicts ?? 0
          }，去重 ${output.duplicates ?? 0}`,
        );
      }
    } catch (err) {
      const message = err instanceof Error ? err.message : '执行失败';
      setError(message);
      pushLog(`✗ ${kind === 'pull' ? '拉取' : '归一'}失败：${message}`);
    } finally {
      setBusy(null);
    }
  }

  if (!canRun) {
    return (
      <div className="run-panel">
        <span className="panel-title">跑批操作 · 只读</span>
        <p className="soft" style={{ fontSize: '0.8rem' }}>
          当前角色不能触发拉取/归一（后端 403），可查看下方最近一次跑批结果。
        </p>
      </div>
    );
  }

  return (
    <div className="run-panel">
      <div className="toolbar" style={{ justifyContent: 'space-between' }}>
        <span className="panel-title">跑批操作台</span>
        <div className="toolbar-group">
          <button className="btn btn-small" disabled={busy !== null} onClick={() => run('pull')}>
            {busy === 'pull' ? '拉取中…' : '拉取轨迹'}
          </button>
          <button className="btn btn-small btn-primary" disabled={busy !== null} onClick={() => run('normalize')}>
            {busy === 'normalize' ? '归一重算…' : '归一重算'}
          </button>
        </div>
      </div>
      {result ? (
        <div className="metric-grid">
          <MetricTile
            label="覆盖率"
            value={result.coverage_percent !== undefined ? `${result.coverage_percent}` : result.events_fetched ?? '—'}
            unit={result.coverage_percent !== undefined ? '%' : '事件'}
            accent
          />
          <MetricTile label="冲突" value={result.conflicts ?? result.events_inserted ?? '—'} hint="非法回退" />
          <MetricTile label="429 退避" value={result.rate_limit_hits ?? 0} hint="mock 限流" />
          <MetricTile label="耗时" value={((result.duration_ms ?? 0) / 1000).toFixed(2)} unit="s" />
        </div>
      ) : null}
      {error ? (
        <p className="form-error" style={{ margin: 0 }}>
          {error}
        </p>
      ) : null}
      <div className="run-log">
        {log.length === 0 ? <span>等待执行（拉取会触发 2 次 mock 429 退避）…</span> : log.map((line, index) => (
          <span key={`${line}-${index}`} className={line.includes('429') ? 'warn' : undefined}>
            {line}
          </span>
        ))}
      </div>
    </div>
  );
}
