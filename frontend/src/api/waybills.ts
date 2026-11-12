import type { WaybillDetail, WaybillList } from '../types/models';
import { http } from './client';

export interface WaybillQuery {
  status?: string;
  carrier_code?: string;
  q?: string;
  page?: number;
  size?: number;
}

export const waybillsApi = {
  list: (query: WaybillQuery) => {
    const params = new URLSearchParams();
    if (query.status) params.set('status', query.status);
    if (query.carrier_code) params.set('carrier_code', query.carrier_code);
    if (query.q) params.set('q', query.q);
    params.set('page', String(query.page ?? 1));
    params.set('size', String(query.size ?? 25));
    return http.get<WaybillList>(`/waybills?${params.toString()}`);
  },
  detail: (id: number) => http.get<WaybillDetail>(`/waybills/${id}`),
};
