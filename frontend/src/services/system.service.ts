import { api } from './api';

export interface ModelMetadata {
  id: string;
  model_name: string;
  model_version: string;
  algorithm: string;
  is_active: boolean;
  accuracy?: number;
  precision_score?: number;
  recall_score?: number;
  f1_score?: number;
  auc_roc?: number;
  avg_latency_ms?: number;
  threshold_allow?: number;
  threshold_challenge?: number;
  threshold_review?: number;
  hyperparameters?: Record<string, any>;
  feature_list?: string[];
  created_at: string;
}

export interface ReadinessData {
  status: string;
  database: string;
  redis: string;
  models_loaded: boolean;
  timestamp: string;
}

export const systemService = {
  async getHealth(): Promise<{ status: string; app: string; version: string; env: string }> {
    const response = await api.get('/system/health');
    return response.data;
  },

  async getReadiness(): Promise<ReadinessData> {
    const response = await api.get<ReadinessData>('/system/readiness');
    return response.data;
  },

  async getModels(): Promise<ModelMetadata[]> {
    const response = await api.get<ModelMetadata[]>('/system/models');
    return response.data;
  },
};
