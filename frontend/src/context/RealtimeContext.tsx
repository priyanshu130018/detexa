import React, { createContext, useContext, useEffect, useState, useCallback } from 'react';
import {
  realtimeService,
  RealtimeConnectionState,
  RealtimeEventType,
  EventCallback,
} from '../services/realtime.service';
import { useAuth } from './AuthContext';
import { api } from '../services/api';
import { Alert, DecisionAction, RiskLevel, Transaction } from '../types';

interface RealtimeContextType {
  connectionState: RealtimeConnectionState;
  reconnectAttempts: number;
  latestTransaction: Transaction | null;
  latestAlert: Alert | null;
  latestDecision: any | null;
  latestStatus: any | null;
  reconnect: () => void;
  simulateEvent: (eventType: string, payload?: Record<string, any>) => Promise<any>;
  subscribe: (eventType: RealtimeEventType, callback: EventCallback) => () => void;
}

const RealtimeContext = createContext<RealtimeContextType | undefined>(undefined);

export const RealtimeProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [connectionState, setConnectionState] = useState<RealtimeConnectionState>(
    realtimeService.getState()
  );
  const [reconnectAttempts, setReconnectAttempts] = useState<number>(0);
  const [latestTransaction, setLatestTransaction] = useState<Transaction | null>(null);
  const [latestAlert, setLatestAlert] = useState<Alert | null>(null);
  const [latestDecision, setLatestDecision] = useState<any | null>(null);
  const [latestStatus, setLatestStatus] = useState<any | null>(null);

  useEffect(() => {
    // Listen for state changes
    const unsubState = realtimeService.onStateChange((state, attempt) => {
      setConnectionState(state);
      setReconnectAttempts(attempt);
    });

    // Event listeners
    const unsubTx = realtimeService.on('new_transaction', (data) => {
      setLatestTransaction(data as Transaction);
    });

    const unsubAlert = realtimeService.on('fraud_alert', (data) => {
      setLatestAlert(data as Alert);
    });

    const unsubDec = realtimeService.on('decision_event', (data) => {
      setLatestDecision(data);
    });

    const unsubStatus = realtimeService.on('status_change', (data) => {
      setLatestStatus(data);
    });

    if (isAuthenticated) {
      realtimeService.connect();
    } else {
      realtimeService.disconnect();
    }

    return () => {
      unsubState();
      unsubTx();
      unsubAlert();
      unsubDec();
      unsubStatus();
    };
  }, [isAuthenticated]);

  const reconnect = useCallback(() => {
    realtimeService.connect();
  }, []);

  const simulateEvent = useCallback(async (eventType: string, payload?: Record<string, any>) => {
    try {
      const response = await api.post('/realtime/simulate', {
        event_type: eventType,
        payload,
      });
      return response.data;
    } catch (err) {
      console.error('Failed to simulate event:', err);
      throw err;
    }
  }, []);

  const subscribe = useCallback((eventType: RealtimeEventType, callback: EventCallback) => {
    return realtimeService.on(eventType, callback);
  }, []);

  return (
    <RealtimeContext.Provider
      value={{
        connectionState,
        reconnectAttempts,
        latestTransaction,
        latestAlert,
        latestDecision,
        latestStatus,
        reconnect,
        simulateEvent,
        subscribe,
      }}
    >
      {children}
    </RealtimeContext.Provider>
  );
};

export const useRealtime = () => {
  const context = useContext(RealtimeContext);
  if (!context) {
    throw new Error('useRealtime must be used within a RealtimeProvider');
  }
  return context;
};
