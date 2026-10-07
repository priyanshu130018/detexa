import { api } from './api';

export interface FeatureSchemaMetadata {
  schema_version: string;
  total_features: number;
  feature_names: string[];
  groups: {
    transaction: { count: number; features: string[] };
    temporal_cyclical: { count: number; features: string[] };
    behavioral_client: { count: number; features: string[] };
    redis_realtime_hot: { count: number; features: string[] };
    neo4j_graph_risk: { count: number; features: string[] };
  };
}

export interface HotFeaturesResponse {
  user_key: string;
  features: Record<string, any>;
  ml_features: Record<string, number>;
}

export const featureService = {
  async getHotFeatures(userKey: string, params?: Record<string, any>): Promise<HotFeaturesResponse> {
    const response = await api.get<HotFeaturesResponse>(`/features/${userKey}`, { params });
    return response.data;
  },

  async getUserSummary(userKey: string): Promise<Record<string, any>> {
    const response = await api.get(`/features/${userKey}/summary`);
    return response.data;
  },

  async getSchemaMetadata(): Promise<FeatureSchemaMetadata> {
    const response = await api.get<FeatureSchemaMetadata>('/features/schema/metadata');
    return response.data;
  },

  async getUnifiedVector(userKey: string, params?: Record<string, any>): Promise<Record<string, any>> {
    const response = await api.get(`/features/vector/${userKey}`, { params });
    return response.data;
  },

  async getHealth(): Promise<Record<string, any>> {
    const response = await api.get('/features/health/status');
    return response.data;
  },
};
