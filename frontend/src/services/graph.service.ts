import { api } from './api';
import { FraudRing, GraphRiskFeatures, SubgraphData } from '../types';

export const graphService = {
  async getGraphFeatures(userId: string, deviceFp?: string, ipAddress?: string): Promise<{ graph_features: GraphRiskFeatures; ml_features: Record<string, number> }> {
    const response = await api.get(`/graph/features/${userId}`, {
      params: { device_fingerprint: deviceFp, ip_address: ipAddress },
    });
    return response.data;
  },

  async getFraudRings(minUsers: number = 2, limit: number = 20): Promise<FraudRing[]> {
    const response = await api.get<FraudRing[]>('/graph/fraud-rings', {
      params: { min_users: minUsers, limit },
    });
    return response.data;
  },

  async getSubgraph(entityType: string, entityId: string, depth: number = 2): Promise<SubgraphData> {
    const response = await api.get<SubgraphData>(`/graph/subgraph/${entityType}/${encodeURIComponent(entityId)}`, {
      params: { depth },
    });
    return response.data;
  },

  async getHealth(): Promise<any> {
    const response = await api.get('/graph/health');
    return response.data;
  },
};
