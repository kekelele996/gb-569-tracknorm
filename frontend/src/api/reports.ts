import type { AuditLog, QualityRow } from '../types/models';
import { downloadTextFile } from '../utils/csv';
import { http } from './client';

export const reportsApi = {
  quality: () => http.get<{ items: QualityRow[] }>('/reports/quality'),
  audit: (limit = 40) => http.get<{ items: AuditLog[]; total: number }>(`/reports/audit?limit=${limit}`),
  pullLogs: (limit = 10) => http.get<{ items: AuditLog[]; total: number }>(`/reports/pull-logs?limit=${limit}`),
  exportDelayNotices: async (): Promise<number> => {
    const content = await http.text('/reports/delay-notices.csv');
    const rows = content.trim().split('\n').length - 1;
    downloadTextFile('tracknorm-delay-notices.csv', content);
    return rows;
  },
};
