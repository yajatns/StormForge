import apiClient from './api';
import { 
  Job, 
  JobCreateRequest, 
  JobStopRequest, 
  JobListParams, 
  JobListResponse,
  JobStats 
} from '../types/job';

export class JobService {
  static async createJob(job: JobCreateRequest): Promise<Job> {
    const response = await apiClient.post<Job>('/jobs/', job);
    return response.data;
  }

  static async getJobs(params: JobListParams = {}): Promise<JobListResponse> {
    const response = await apiClient.get<JobListResponse>('/jobs/', params);
    return response.data;
  }

  static async getJob(jobId: string): Promise<Job> {
    const response = await apiClient.get<Job>(`/jobs/${jobId}`);
    return response.data;
  }

  static async stopJob(jobId: string, options: JobStopRequest = {}): Promise<void> {
    await apiClient.post(`/jobs/${jobId}/stop`, options);
  }

  static async deleteJob(jobId: string): Promise<void> {
    await apiClient.delete(`/jobs/${jobId}`);
  }

  static async getJobOutput(jobId: string): Promise<{stdout: string, stderr: string}> {
    const response = await apiClient.get<{stdout: string, stderr: string}>(`/jobs/${jobId}/output`);
    return response.data;
  }

  static async getJobStats(): Promise<JobStats> {
    const response = await apiClient.get<JobStats>('/jobs/stats');
    return response.data;
  }

  static async validateTargets(targets: string[]): Promise<{valid: boolean, errors: string[]}> {
    const response = await apiClient.post<{valid: boolean, errors: string[]}>('/jobs/validate-targets', {
      targets
    });
    return response.data;
  }

  static async getJobHistory(
    jobId: string, 
    params: { skip?: number; limit?: number } = {}
  ): Promise<any[]> {
    const response = await apiClient.get(`/jobs/${jobId}/history`, params);
    return response.data;
  }
}

export default JobService;