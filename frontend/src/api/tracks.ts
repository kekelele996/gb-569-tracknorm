import type { LastRuns, NormalizeStats, PullStats } from '../types/models';
import { http } from './client';

export const tracksApi = {
  pull: (carrierCodes?: string[]) =>
    http.post<PullStats>('/tracks/pull', { carrier_codes: carrierCodes, force: true }),
  normalize: (version?: number) => http.post<NormalizeStats>('/tracks/normalize', { version: version ?? null }),
  lastRuns: () => http.get<LastRuns>('/tracks/last-runs'),
};
