import { api } from './api';
import { BehaviorLog, BehaviorStats } from '../types';

export const behaviorService = {
  async listBehaviorLogs(limit = 100, skip = 0, page = 1, page_size = 20): Promise<BehaviorLog[]> {
    const { data } = await api.get<any>('/behavior/logs', { params: { limit, skip, page, page_size } });
    if (data && Array.isArray(data.items)) {
      return data.items;
    }
    return Array.isArray(data) ? data : [];
  },

  async getBehaviorStats(): Promise<BehaviorStats> {
    const { data } = await api.get<BehaviorStats>('/behavior/stats');
    return data;
  },
};
