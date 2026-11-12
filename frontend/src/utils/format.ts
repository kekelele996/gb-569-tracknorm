export function fmtPercent(value: number | null | undefined, digits = 1): string {
  if (value === null || value === undefined) return '—';
  return `${(value * 100).toFixed(digits)}%`;
}

export function fmtNumber(value: number | null | undefined, digits = 2): string {
  if (value === null || value === undefined) return '—';
  return value.toFixed(digits);
}

export function fmtDateTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fmtTime(value: string | null | undefined): string {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

export function fmtHours(minutes: number | null | undefined): string {
  if (minutes === null || minutes === undefined) return '—';
  return `${(minutes / 60).toFixed(1)} h`;
}

export function fmtSignedHours(hours: number | null | undefined): string {
  if (hours === null || hours === undefined) return '—';
  const sign = hours > 0 ? '+' : '';
  return `${sign}${hours.toFixed(1)} h`;
}

export function shortId(value: string | null | undefined): string {
  if (!value) return '—';
  return value.length > 22 ? `${value.slice(0, 22)}…` : value;
}

export function classNames(...values: (string | false | null | undefined)[]): string {
  return values.filter(Boolean).join(' ');
}
