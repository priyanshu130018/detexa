export type RealtimeConnectionState =
  | 'connecting'
  | 'connected'
  | 'reconnecting'
  | 'disconnected'
  | 'unavailable';

export type RealtimeEventType =
  | 'new_transaction'
  | 'fraud_alert'
  | 'decision_event'
  | 'status_change'
  | 'heartbeat'
  | 'connection_established'
  | 'all';

export type EventCallback = (data: any, eventType: string) => void;
export type StateChangeCallback = (state: RealtimeConnectionState, attempt: number) => void;

class RealtimeService {
  private static instance: RealtimeService | null = null;
  private ws: WebSocket | null = null;
  private sse: EventSource | null = null;
  private listeners: Map<string, Set<EventCallback>> = new Map();
  private stateListeners: Set<StateChangeCallback> = new Set();
  
  private state: RealtimeConnectionState = 'disconnected';
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 10;
  private baseReconnectDelayMs = 1000;
  private maxReconnectDelayMs = 15000;
  private reconnectTimer: any = null;
  private watchdogTimer: any = null;
  private lastMessageTimestamp = Date.now();
  private watchdogTimeoutMs = 35000; // If no ping/event in 35s, socket is stale
  private useSSEFallback = false;
  private isManuallyClosed = false;

  private constructor() {
    // Singleton
  }

  public static getInstance(): RealtimeService {
    if (!RealtimeService.instance) {
      RealtimeService.instance = new RealtimeService();
    }
    return RealtimeService.instance;
  }

  public getState(): RealtimeConnectionState {
    return this.state;
  }

  public getReconnectAttempts(): number {
    return this.reconnectAttempts;
  }

  /**
   * Subscribe to real-time events.
   */
  public on(eventType: RealtimeEventType, callback: EventCallback): () => void {
    if (!this.listeners.has(eventType)) {
      this.listeners.set(eventType, new Set());
    }
    this.listeners.get(eventType)!.add(callback);

    // Return un-subscribe function
    return () => {
      this.listeners.get(eventType)?.delete(callback);
    };
  }

  /**
   * Subscribe to connection state changes.
   */
  public onStateChange(callback: StateChangeCallback): () => void {
    this.stateListeners.add(callback);
    callback(this.state, this.reconnectAttempts);
    return () => {
      this.stateListeners.delete(callback);
    };
  }

  private setState(newState: RealtimeConnectionState) {
    if (this.state !== newState) {
      this.state = newState;
      this.stateListeners.forEach((cb) => {
        try {
          cb(newState, this.reconnectAttempts);
        } catch (e) {
          console.error('Error in state listener:', e);
        }
      });
    }
  }

  /**
   * Connect to real-time stream (WebSocket with auto SSE fallback).
   */
  public connect() {
    this.isManuallyClosed = false;
    if (this.state === 'connected' || this.state === 'connecting') {
      return;
    }

    if (this.useSSEFallback) {
      this.connectSSE();
    } else {
      this.connectWebSocket();
    }
  }

  private getWebSocketUrl(): string {
    const apiBase = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000/api/v1';
    let wsUrl = apiBase.replace(/^http/, 'ws');
    if (wsUrl.endsWith('/api/v1')) {
      wsUrl += '/ws/events';
    } else {
      wsUrl += '/api/v1/ws/events';
    }
    const token = localStorage.getItem('detexa_token');
    if (token) {
      wsUrl += `?token=${encodeURIComponent(token)}`;
    }
    return wsUrl;
  }

  private getSSEUrl(): string {
    const apiBase = (import.meta.env.VITE_API_BASE_URL as string) || 'http://localhost:8000/api/v1';
    if (apiBase.endsWith('/api/v1')) {
      return `${apiBase}/events/stream`;
    }
    return `${apiBase}/api/v1/events/stream`;
  }

  private connectWebSocket() {
    this.cleanup();
    this.setState(this.reconnectAttempts > 0 ? 'reconnecting' : 'connecting');

    try {
      const url = this.getWebSocketUrl();
      this.ws = new WebSocket(url);

      this.ws.onopen = () => {
        this.reconnectAttempts = 0;
        this.lastMessageTimestamp = Date.now();
        this.setState('connected');
        this.startWatchdog();
        // Send initial channel subscription
        try {
          this.ws?.send(JSON.stringify({ action: 'subscribe', channel: 'all' }));
        } catch (_) {}
      };

      this.ws.onmessage = (event) => {
        this.lastMessageTimestamp = Date.now();
        try {
          const parsed = JSON.parse(event.data);
          const eventType = parsed.event || 'unknown';
          const data = parsed.data || parsed;
          this.emit(eventType, data);
        } catch (e) {
          console.warn('Failed to parse WS event payload:', e);
        }
      };

      this.ws.onerror = (err) => {
        console.warn('WebSocket encountered error:', err);
        // If initial connection fails multiple times, switch to SSE fallback
        if (this.reconnectAttempts >= 3) {
          this.useSSEFallback = true;
        }
      };

      this.ws.onclose = (event) => {
        this.stopWatchdog();
        if (!this.isManuallyClosed) {
          this.handleDisconnect();
        } else {
          this.setState('disconnected');
        }
      };
    } catch (e) {
      console.error('Could not instantiate WebSocket:', e);
      this.useSSEFallback = true;
      this.handleDisconnect();
    }
  }

  private connectSSE() {
    this.cleanup();
    this.setState(this.reconnectAttempts > 0 ? 'reconnecting' : 'connecting');

    try {
      const url = this.getSSEUrl();
      this.sse = new EventSource(url);

      this.sse.onopen = () => {
        this.reconnectAttempts = 0;
        this.lastMessageTimestamp = Date.now();
        this.setState('connected');
        this.startWatchdog();
      };

      this.sse.onmessage = (event) => {
        this.lastMessageTimestamp = Date.now();
        try {
          const parsed = JSON.parse(event.data);
          const eventType = parsed.event || 'unknown';
          const data = parsed.data || parsed;
          this.emit(eventType, data);
        } catch (e) {
          console.warn('Failed to parse SSE payload:', e);
        }
      };

      this.sse.onerror = (err) => {
        console.warn('SSE encountered error:', err);
        this.stopWatchdog();
        if (!this.isManuallyClosed) {
          this.handleDisconnect();
        }
      };
    } catch (e) {
      console.error('Could not instantiate SSE EventSource:', e);
      this.handleDisconnect();
    }
  }

  private handleDisconnect() {
    this.cleanup();
    this.reconnectAttempts += 1;

    if (this.reconnectAttempts > this.maxReconnectAttempts) {
      this.setState('unavailable');
      return;
    }

    this.setState('reconnecting');

    // Calculate exponential backoff with jitter
    const delay = Math.min(
      this.baseReconnectDelayMs * Math.pow(1.5, this.reconnectAttempts) + Math.random() * 500,
      this.maxReconnectDelayMs
    );

    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
    }

    this.reconnectTimer = setTimeout(() => {
      if (!this.isManuallyClosed) {
        this.connect();
      }
    }, delay);
  }

  /**
   * Watchdog timer to detect stale connections if no heartbeat was received.
   */
  private startWatchdog() {
    this.stopWatchdog();
    this.watchdogTimer = setInterval(() => {
      const now = Date.now();
      if (now - this.lastMessageTimestamp > this.watchdogTimeoutMs) {
        console.warn('Realtime connection is stale (heartbeat timeout). Reconnecting...');
        this.handleDisconnect();
      } else if (this.ws && this.ws.readyState === WebSocket.OPEN) {
        // Send client ping
        try {
          this.ws.send(JSON.stringify({ action: 'ping' }));
        } catch (_) {}
      }
    }, 12000);
  }

  private stopWatchdog() {
    if (this.watchdogTimer) {
      clearInterval(this.watchdogTimer);
      this.watchdogTimer = null;
    }
  }

  private emit(eventType: string, data: any) {
    // Specific event listeners
    const listeners = this.listeners.get(eventType);
    if (listeners) {
      listeners.forEach((cb) => {
        try {
          cb(data, eventType);
        } catch (e) {
          console.error(`Error in ${eventType} callback:`, e);
        }
      });
    }

    // Catch-all 'all' listeners
    const allListeners = this.listeners.get('all');
    if (allListeners) {
      allListeners.forEach((cb) => {
        try {
          cb(data, eventType);
        } catch (e) {
          console.error('Error in catch-all callback:', e);
        }
      });
    }
  }

  public disconnect() {
    this.isManuallyClosed = true;
    this.cleanup();
    this.setState('disconnected');
  }

  private cleanup() {
    this.stopWatchdog();
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      try {
        this.ws.onclose = null;
        this.ws.onerror = null;
        this.ws.close();
      } catch (_) {}
      this.ws = null;
    }
    if (this.sse) {
      try {
        this.sse.onerror = null;
        this.sse.close();
      } catch (_) {}
      this.sse = null;
    }
  }
}

export const realtimeService = RealtimeService.getInstance();
