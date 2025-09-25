export interface User {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'operator' | 'read_only';
  enabled: boolean;
  created_at: string;
  last_login?: string;
  quotas?: UserQuotas;
}

export interface UserQuotas {
  max_concurrent_jobs?: number;
  max_jobs_per_hour?: number;
  max_targets_per_job?: number;
  max_pps?: number;
  max_duration?: number;
}

export interface AuthToken {
  access_token: string;
  token_type: string;
  expires_in?: number;
}

export interface ApiKey {
  id: string;
  name: string;
  key: string;
  scopes: string[];
  enabled: boolean;
  created_at: string;
  last_used?: string;
  expires_at?: string;
}