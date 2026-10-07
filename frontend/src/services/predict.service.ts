import { api } from './api';
import { BatchCreditFraudResult, BehaviorPredictionResult, FraudPredictionResult } from '../types';

export const predictService = {
  async predictCredit(payload: Record<string, any>): Promise<FraudPredictionResult> {
    const { data } = await api.post<FraudPredictionResult>('/predict/credit', payload);
    return data;
  },

  async predictCreditBatch(transactions: Record<string, any>[]): Promise<BatchCreditFraudResult> {
    const { data } = await api.post<BatchCreditFraudResult>('/predict/credit/batch', { transactions });
    return data;
  },

  async predictBehavior(payload: Record<string, any>): Promise<BehaviorPredictionResult> {
    const { data } = await api.post<BehaviorPredictionResult>('/predict/behavior', payload);
    return data;
  },
};
