import type { MappingRuleList, MappingStats, MappingVersion } from '../types/models';
import { http } from './client';

export const mappingsApi = {
  versions: () => http.get<{ versions: MappingVersion[]; active_version: number }>('/mappings/versions'),
  rules: (version?: number) =>
    http.get<MappingRuleList>(`/mappings${version ? `?version=${version}` : ''}`),
  evaluate: (version?: number) =>
    http.get<MappingStats>(`/mappings/evaluate${version ? `?version=${version}` : ''}`),
  createVersion: (baseVersion: number, note?: string) =>
    http.post<{ version: number; copied_rules: number; added_rules: number; note: string }>('/mappings/versions', {
      base_version: baseVersion,
      note,
    }),
  activate: (version: number) => http.post<{ version: number; rules: number }>('/mappings/activate', { version }),
};
