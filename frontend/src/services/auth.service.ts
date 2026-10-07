import { api } from './api';
import { TokenResponse, User } from '../types';

export const authService = {
  async login(email: string, password: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>('/auth/login', { email, password });
    return data;
  },

  async register(name: string, email: string, mobile?: string, password?: string): Promise<TokenResponse> {
    const { data } = await api.post<TokenResponse>('/auth/register', {
      name,
      email,
      mobile,
      password,
    });
    return data;
  },

  async getMe(): Promise<User> {
    const { data } = await api.get<User>('/auth/me');
    return data;
  },

  async listUsers(limit = 50, skip = 0): Promise<User[]> {
    const { data } = await api.get<User[]>('/auth/users', { params: { limit, skip } });
    return data;
  },

  async updateUserStatus(userId: string, isActive: boolean): Promise<User> {
    const { data } = await api.put<User>(`/auth/users/${userId}/status`, null, {
      params: { is_active: isActive },
    });
    return data;
  },
};
