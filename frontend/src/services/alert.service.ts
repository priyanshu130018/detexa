import { api } from './api';
import { Alert, AlertStatus, DashboardStats, RiskLevel } from '../types';

export interface AlertQueryParams {
  limit?: number;
  skip?: number;
  status?: AlertStatus;
  risk_level?: RiskLevel;
  alert_type?: string;
}

export const alertService = {
  async getAlerts(params?: AlertQueryParams): Promise<Alert[]> {
    const response = await api.get<any>('/alerts', { params });
    if (response.data && Array.isArray(response.data.items)) {
      return response.data.items;
    }
    return Array.isArray(response.data) ? response.data : [];
  },

  async getAlertById(id: string): Promise<Alert> {
    const response = await api.get<Alert>(`/alerts/${id}`);
    return response.data;
  },

  async updateAlertStatus(id: string, status: AlertStatus, notes?: string): Promise<Alert> {
    const response = await api.patch<Alert>(`/alerts/${id}/status`, { status, notes });
    return response.data;
  },

  async getDashboardStats(): Promise<DashboardStats> {
    const response = await api.get<DashboardStats>('/alerts/stats');
    return response.data;
  },
};
