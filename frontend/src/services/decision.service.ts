import { api } from './api';
import { DecisionStats } from '../types';

export interface DecisionQueryParams {
  page?: number;
  page_size?: number;
  decision?: string;
  risk_level?: string;
}

export const decisionService = {
  async getDecisions(params?: DecisionQueryParams): Promise<any> {
    const response = await api.get('/decisions', { params });
    return response.data;
  },

  async getDecisionStats(): Promise<DecisionStats> {
    const response = await api.get<DecisionStats>('/decisions/stats');
    return response.data;
  },

  async getRulesPolicy(): Promise<any> {
    const response = await api.get('/decisions/rules/policy');
    return response.data;
  },

  async evaluateContext(params: Record<string, any>): Promise<any> {
    const response = await api.post('/decisions/evaluate/context', null, { params });
    return response.data;
  },

  async overrideDecision(id: string, newDecision: string, reason: string): Promise<any> {
    const response = await api.post(`/decisions/${id}/override`, {
      new_decision: newDecision,
      reason,
    });
    return response.data;
  },
};
