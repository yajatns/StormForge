export interface TargetGroup {
  id: string;
  name: string;
  targets: string[];
  description?: string;
  created_at: string;
  updated_at: string;
  created_by: number;
}

export interface AllowlistEntry {
  id: string;
  cidr: string;
  description?: string;
  created_at: string;
  created_by: number;
}

export interface SystemMetrics {
  jobs: {
    total: number;
    running: number;
    pending: number;
    completed_today: number;
    failed_today: number;
  };
  system: {
    cpu_usage: number;
    memory_usage: number;
    disk_usage: number;
    uptime: number;
  };
  network: {
    packets_sent_today: number;
    bytes_sent_today: number;
    active_targets: number;
  };
  users: {
    total_users: number;
    active_sessions: number;
    api_requests_today: number;
  };
}

export interface AuditLog {
  id: string;
  action: string;
  resource_type: string;
  resource_id?: string;
  user_id: number;
  username: string;
  details: Record<string, any>;
  client_ip?: string;
  user_agent?: string;
  timestamp: string;
}