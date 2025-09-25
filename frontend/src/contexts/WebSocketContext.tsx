import React, { createContext, useContext, useEffect, useState, ReactNode, useRef } from 'react';
import { useAuth } from './AuthContext';
import { WebSocketEventType, JobStatusUpdate, SystemEvent } from '../types/websocket';

interface WebSocketState {
  connected: boolean;
  connecting: boolean;
  error: string | null;
  lastMessage: WebSocketEventType | null;
}

interface WebSocketContextValue extends WebSocketState {
  connect: (type?: 'global' | 'job', jobId?: string) => void;
  disconnect: () => void;
  sendMessage: (message: any) => void;
  subscribeToJobUpdates: (jobId: string, callback: (update: JobStatusUpdate) => void) => () => void;
  subscribeToSystemEvents: (callback: (event: SystemEvent) => void) => () => void;
}

const WebSocketContext = createContext<WebSocketContextValue | undefined>(undefined);

export const useWebSocket = (): WebSocketContextValue => {
  const context = useContext(WebSocketContext);
  if (!context) {
    throw new Error('useWebSocket must be used within a WebSocketProvider');
  }
  return context;
};

interface WebSocketProviderProps {
  children: ReactNode;
}

export const WebSocketProvider: React.FC<WebSocketProviderProps> = ({ children }) => {
  const { isAuthenticated } = useAuth();
  const [state, setState] = useState<WebSocketState>({
    connected: false,
    connecting: false,
    error: null,
    lastMessage: null,
  });

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const subscriptionsRef = useRef<{
    jobUpdates: Map<string, (update: JobStatusUpdate) => void>;
    systemEvents: Set<(event: SystemEvent) => void>;
  }>({
    jobUpdates: new Map(),
    systemEvents: new Set(),
  });

  const getWebSocketUrl = (type: 'global' | 'job' = 'global', jobId?: string): string => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const token = localStorage.getItem('auth_token');
    
    let path = '';
    if (type === 'job' && jobId) {
      path = `/api/v1/ws/job/${jobId}`;
    } else {
      path = '/api/v1/ws/monitor';
    }
    
    return `${protocol}//${host}${path}?token=${token}`;
  };

  const handleMessage = (event: MessageEvent) => {
    try {
      const message: WebSocketEventType = JSON.parse(event.data);
      
      setState(prev => ({ ...prev, lastMessage: message }));

      // Handle different message types
      switch (message.type) {
        case 'job_status_update':
          const jobUpdate = message as JobStatusUpdate;
          const jobCallback = subscriptionsRef.current.jobUpdates.get(jobUpdate.job_id);
          if (jobCallback) {
            jobCallback(jobUpdate);
          }
          break;

        case 'system_event':
          const systemEvent = message as SystemEvent;
          subscriptionsRef.current.systemEvents.forEach(callback => {
            callback(systemEvent);
          });
          break;

        case 'connection_established':
          console.log('WebSocket connection established:', message);
          break;

        case 'pong':
          // Handle pong response
          break;

        default:
          console.log('Unknown WebSocket message type:', message.type);
      }
    } catch (error) {
      console.error('Failed to parse WebSocket message:', error);
    }
  };

  const handleOpen = () => {
    setState(prev => ({ 
      ...prev, 
      connected: true, 
      connecting: false, 
      error: null 
    }));
    
    // Start ping interval
    pingIntervalRef.current = setInterval(() => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'ping' }));
      }
    }, 30000);

    console.log('WebSocket connected');
  };

  const handleClose = (event: CloseEvent) => {
    setState(prev => ({ 
      ...prev, 
      connected: false, 
      connecting: false,
      error: event.code !== 1000 ? `Connection closed: ${event.reason}` : null
    }));

    // Clear intervals
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    console.log('WebSocket disconnected:', event.code, event.reason);

    // Auto-reconnect if authenticated and not a normal closure
    if (isAuthenticated && event.code !== 1000) {
      reconnectTimeoutRef.current = setTimeout(() => {
        connect();
      }, 5000);
    }
  };

  const handleError = (event: Event) => {
    setState(prev => ({ 
      ...prev, 
      connecting: false,
      error: 'Connection error occurred' 
    }));
    console.error('WebSocket error:', event);
  };

  const connect = (type: 'global' | 'job' = 'global', jobId?: string) => {
    if (!isAuthenticated) return;

    if (wsRef.current) {
      wsRef.current.close();
    }

    setState(prev => ({ ...prev, connecting: true, error: null }));

    try {
      const url = getWebSocketUrl(type, jobId);
      wsRef.current = new WebSocket(url);
      
      wsRef.current.onopen = handleOpen;
      wsRef.current.onmessage = handleMessage;
      wsRef.current.onclose = handleClose;
      wsRef.current.onerror = handleError;
    } catch (error) {
      setState(prev => ({ 
        ...prev, 
        connecting: false, 
        error: 'Failed to create WebSocket connection' 
      }));
    }
  };

  const disconnect = () => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close(1000, 'Manual disconnect');
      wsRef.current = null;
    }

    setState(prev => ({ 
      ...prev, 
      connected: false, 
      connecting: false, 
      error: null 
    }));
  };

  const sendMessage = (message: any) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(message));
    }
  };

  const subscribeToJobUpdates = (
    jobId: string, 
    callback: (update: JobStatusUpdate) => void
  ): (() => void) => {
    subscriptionsRef.current.jobUpdates.set(jobId, callback);
    return () => {
      subscriptionsRef.current.jobUpdates.delete(jobId);
    };
  };

  const subscribeToSystemEvents = (
    callback: (event: SystemEvent) => void
  ): (() => void) => {
    subscriptionsRef.current.systemEvents.add(callback);
    return () => {
      subscriptionsRef.current.systemEvents.delete(callback);
    };
  };

  // Auto-connect when authenticated
  useEffect(() => {
    if (isAuthenticated) {
      connect();
    } else {
      disconnect();
    }

    return () => {
      disconnect();
    };
  }, [isAuthenticated]);

  const value: WebSocketContextValue = {
    ...state,
    connect,
    disconnect,
    sendMessage,
    subscribeToJobUpdates,
    subscribeToSystemEvents,
  };

  return (
    <WebSocketContext.Provider value={value}>
      {children}
    </WebSocketContext.Provider>
  );
};