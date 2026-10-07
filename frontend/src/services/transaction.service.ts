import { api } from './api';
import { Transaction } from '../types';

export interface TransactionQueryParams {
  limit?: number;
  skip?: number;
  is_fraud?: boolean;
  risk_level?: string;
  search?: string;
}

export const transactionService = {
  async getTransactions(params?: TransactionQueryParams): Promise<Transaction[]> {
    const response = await api.get<Transaction[]>('/transactions', { params });
    return response.data;
  },

  async getTransactionById(id: string): Promise<Transaction> {
    const response = await api.get<Transaction>(`/transactions/${id}`);
    return response.data;
  },
};
