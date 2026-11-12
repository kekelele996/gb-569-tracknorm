import { SEVERITY_LABEL, STATUS_LABEL, STATUS_TONE } from '../../constants/enums';

interface Props {
  status?: string;
  label?: string;
  tone?: string;
  severity?: string;
  className?: string;
}

/** 状态灯：8 个归一状态与 3 级停滞等级共用（总览 / 详情 / 预警 / 质量页）。 */
export default function StatusLamp({ status, label, tone, severity, className }: Props) {
  const resolvedTone = severity ? (severity === 'critical' ? 'danger' : severity === 'alert' ? 'warn' : 'neutral') : tone ?? (status ? STATUS_TONE[status] : 'neutral');
  const resolvedLabel = label ?? (status ? STATUS_LABEL[status] ?? status : severity ? SEVERITY_LABEL[severity] ?? severity : '—');
  const classes = ['lamp', `tone-${resolvedTone}`];
  if (severity) classes.push(`severity-${severity}`);
  if (className) classes.push(className);
  return (
    <span className={classes.join(' ')}>
      <span className="lamp-dot" />
      <span>{resolvedLabel}</span>
    </span>
  );
}
