import type { Carrier } from '../types/models';
import { http } from './client';

export const carriersApi = {
  list: () => http.get<{ items: Carrier[] }>('/carriers'),
  update: (id: number, payload: { daily_quota?: number; rate_limit_per_min?: number; is_active?: boolean; note?: string }) =>
    http.patch<Carrier>(`/carriers/${id}`, payload),
};
