interface Props {
  label: string;
  value: React.ReactNode;
  unit?: string;
  hint?: string;
  accent?: boolean;
}

export default function MetricTile({ label, value, unit, hint, accent }: Props) {
  const long = typeof value === 'string' && value.length > 10;
  return (
    <div className={`metric${accent ? ' accent' : ''}`}>
      <span className="metric-label">{label}</span>
      <span className={`metric-value${long ? ' long' : ''}`}>
        {value}
        {unit ? <small>{unit}</small> : null}
      </span>
      {hint ? <span className="metric-hint">{hint}</span> : null}
    </div>
  );
}
