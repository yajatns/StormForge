export interface WebSocketMessage {
  type: string;
  timestamp: string;
  [key: string]: any;
}

export interface JobStatusUpdate extends WebSocketMessage {
  type: 'job_status_update';
  job_id: string;
  data: {
    status: string;
    progress?: number;
    output_lines?: number;
    error_message?: string;
    started_at?: string;
    completed_at?: string;
    pid?: number;
    packets_sent?: number;
    bytes_sent?: number;
  };
}

export interface SystemEvent extends WebSocketMessage {
  type: 'system_event';
  event_type: string;
  level: 'info' | 'warning' | 'error';
  data: Record<string, any>;
}

export interface AdminAction extends WebSocketMessage {
  type: 'admin_action';
  action: string;
  details: Record<string, any>;
  performed_by: number;
}

export interface ConnectionEstablished extends WebSocketMessage {
  type: 'connection_established';
  message: string;
  subscription_type: string;
  job_id?: string;
  server_time: string;
}

export interface PingPong extends WebSocketMessage {
  type: 'ping' | 'pong';
}

export interface SystemStats extends WebSocketMessage {
  type: 'system_stats';
  data: {
    total_connections: number;
    global_subscribers: number;
    job_subscriptions: number;
    connections_by_role: {
      admin: number;
      operator: number;
      read_only: number;
    };
  };
}

export type WebSocketEventType = 
  | JobStatusUpdate
  | SystemEvent
  | AdminAction
  | ConnectionEstablished
  | PingPong
  | SystemStats;