export type JobStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

export type TrafficType = 'icmp' | 'tcp-syn' | 'tcp-ack' | 'tcp-rst' | 'udp';

export type Priority = 'low' | 'normal' | 'high';

export interface Job {
  job_id: string;
  name: string;
  status: JobStatus;
  command: string;
  created_at: string;
  started_at?: string;
  completed_at?: string;
  user_id: number;
  targets: string[];
  traffic_type: TrafficType;
  dst_port?: number;
  src_port?: number;
  pps: number;
  duration?: number;
  packet_count?: number;
  dry_run: boolean;
  priority: Priority;
  tags?: string[];
  packets_sent: number;
  bytes_sent: number;
  progress?: number;
  output_lines?: number;
  error_message?: string;
  pid?: number;
}

export interface JobCreateRequest {
  name: string;
  targets: string[];
  traffic_type: TrafficType;
  dst_port?: number;
  src_port?: number;
  pps: number;
  duration?: number;
  packet_count?: number;
  dry_run?: boolean;
  priority?: Priority;
  tags?: string[];
}

export interface JobStopRequest {
  force?: boolean;
}

export interface JobListParams {
  skip?: number;
  limit?: number;
  status?: JobStatus;
  user_id?: number;
  search?: string;
  tags?: string[];
}

export interface JobListResponse {
  jobs: Job[];
  total: number;
  skip: number;
  limit: number;
}

export interface JobStats {
  total_jobs: number;
  running_jobs: number;
  completed_jobs: number;
  failed_jobs: number;
  total_packets_sent: number;
  total_bytes_sent: number;
}