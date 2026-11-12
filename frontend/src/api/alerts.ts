import type { Alert, AlertSummary } from '../types/models';
import { http } from './client';

export const alertsApi = {
  list: (query: { status?: string; severity?: string } = {}) => {
    const params = new URLSearchParams();
    if (query.status) params.set('status', query.status);
    if (query.severity) params.set('severity', query.severity);
    const suffix = params.toString() ? `?${params.toString()}` : '';
    return http.get<{ items: Alert[]; total: number }>(`/alerts${suffix}`);
  },
  summary: () => http.get<AlertSummary>('/alerts/summary'),
  claim: (id: number, note?: string) => http.post<{ id: number; status: string }>(`/alerts/${id}/claim`, { note }),
  dispose: (id: number, disposition: string, note?: string) =>
    http.post<{ id: number; status: string; disposition: string }>(`/alerts/${id}/dispose`, { disposition, note }),
};
