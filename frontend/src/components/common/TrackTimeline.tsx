import type { TrackEvent } from '../../types/models';
import { MATCH_TYPE_LABEL, STATUS_LABEL, STATUS_TONE } from '../../constants/enums';
import { fmtTime } from '../../utils/format';

interface Props {
  events: TrackEvent[];
  emptyHint?: string;
}

/** 垂直时间轴：归一轨迹（运单详情与预警抽屉共用）。 */
export default function TrackTimeline({ events, emptyHint = '暂无归一轨迹' }: Props) {
  if (!events || events.length === 0) {
    return <p className="loading-line">{emptyHint}</p>;
  }
  return (
    <div className="timeline">
      {events.map((event, index) => {
        const status = event.target_status ?? '';
        return (
          <div className="timeline-item" key={`${event.carrier_event_id}-${index}`}>
            <div className="timeline-time mono">{fmtTime(event.event_time)}</div>
            <div className="timeline-rail">
              <span className={`timeline-dot tone-${STATUS_TONE[status] ?? 'neutral'}`} />
            </div>
            <div className="timeline-body">
              <div className="timeline-line">
                <span className="timeline-status">{STATUS_LABEL[status] ?? status ?? '未映射'}</span>
                <span className="timeline-code">{event.raw_status}</span>
                {event.match_type ? (
                  <span className={`badge badge-${event.match_type}`}>
                    {MATCH_TYPE_LABEL[event.match_type] ?? event.match_type}
                    {typeof event.score === 'number' ? ` · ${event.score.toFixed(2)}` : ''}
                  </span>
                ) : null}
              </div>
              <div className="timeline-loc">{event.location}</div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
