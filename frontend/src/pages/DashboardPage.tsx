import React, { useEffect, useState } from 'react';
import {
  Box,
  Grid,
  Card,
  CardContent,
  Typography,
  Button,
  Chip,
  List,
  ListItem,
  ListItemText,
  ListItemSecondaryAction,
  IconButton,
  Alert,
} from '@mui/material';
import {
  PlayArrow as StartIcon,
  Stop as StopIcon,
  Refresh as RefreshIcon,
  TrendingUp as StatsIcon,
} from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../contexts/AuthContext';
import { useWebSocket } from '../contexts/WebSocketContext';
import JobService from '../services/jobs';
import { Job, JobStats } from '../types/job';
import LoadingSpinner from '../components/LoadingSpinner';

const DashboardPage: React.FC = () => {
  const { user } = useAuth();
  const { subscribeToJobUpdates, subscribeToSystemEvents } = useWebSocket();
  const navigate = useNavigate();
  
  const [recentJobs, setRecentJobs] = useState<Job[]>([]);
  const [jobStats, setJobStats] = useState<JobStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboardData = async () => {
    try {
      setLoading(true);
      setError(null);
      
      const [jobsResponse, statsResponse] = await Promise.all([
        JobService.getJobs({ limit: 5 }),
        JobService.getJobStats(),
      ]);
      
      setRecentJobs(jobsResponse.jobs);
      setJobStats(statsResponse);
    } catch (error: any) {
      console.error('Failed to fetch dashboard data:', error);
      setError(error.response?.data?.detail || 'Failed to load dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboardData();

    // Subscribe to real-time updates
    const unsubscribeJobs = subscribeToJobUpdates('*', (update) => {
      // Update recent jobs when any job status changes
      setRecentJobs(prev => prev.map(job => 
        job.job_id === update.job_id 
          ? { ...job, status: update.data.status as any, progress: update.data.progress }
          : job
      ));
    });

    const unsubscribeEvents = subscribeToSystemEvents((event) => {
      if (event.event_type === 'job_created' || event.event_type === 'job_completed') {
        // Refresh dashboard data when jobs are created/completed
        fetchDashboardData();
      }
    });

    return () => {
      unsubscribeJobs();
      unsubscribeEvents();
    };
  }, [subscribeToJobUpdates, subscribeToSystemEvents]);

  const getStatusColor = (status: string) => {
    switch (status) {
      case 'running': return 'primary';
      case 'completed': return 'success';
      case 'failed': return 'error';
      case 'cancelled': return 'default';
      default: return 'warning';
    }
  };

  const handleStopJob = async (jobId: string) => {
    try {
      await JobService.stopJob(jobId);
      // Job status will be updated via WebSocket
    } catch (error: any) {
      console.error('Failed to stop job:', error);
      setError(error.response?.data?.detail || 'Failed to stop job');
    }
  };

  if (loading) {
    return <LoadingSpinner message="Loading dashboard..." />;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Dashboard
        </Typography>
        <Box display="flex" gap={2}>
          <Button
            variant="contained"
            startIcon={<StartIcon />}
            onClick={() => navigate('/jobs/create')}
          >
            Create Job
          </Button>
          <Button
            variant="outlined"
            startIcon={<RefreshIcon />}
            onClick={fetchDashboardData}
          >
            Refresh
          </Button>
        </Box>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Grid container spacing={3}>
        {/* Statistics Cards */}
        {jobStats && (
          <>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Total Jobs
                  </Typography>
                  <Typography variant="h4" component="div">
                    {jobStats.total_jobs}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Running Jobs
                  </Typography>
                  <Typography variant="h4" component="div">
                    {jobStats.running_jobs}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Completed Today
                  </Typography>
                  <Typography variant="h4" component="div">
                    {jobStats.completed_jobs}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
            <Grid item xs={12} sm={6} md={3}>
              <Card>
                <CardContent>
                  <Typography color="textSecondary" gutterBottom>
                    Failed Today
                  </Typography>
                  <Typography variant="h4" component="div">
                    {jobStats.failed_jobs}
                  </Typography>
                </CardContent>
              </Card>
            </Grid>
          </>
        )}

        {/* Recent Jobs */}
        <Grid item xs={12}>
          <Card>
            <CardContent>
              <Typography variant="h6" gutterBottom>
                Recent Jobs
              </Typography>
              {recentJobs.length === 0 ? (
                <Typography color="textSecondary">
                  No recent jobs found. {' '}
                  <Button 
                    color="primary" 
                    onClick={() => navigate('/jobs/create')}
                  >
                    Create your first job
                  </Button>
                </Typography>
              ) : (
                <List>
                  {recentJobs.map((job) => (
                    <ListItem key={job.job_id} divider>
                      <ListItemText
                        primary={
                          <Box display="flex" alignItems="center" gap={2}>
                            <Typography variant="subtitle1">
                              {job.name}
                            </Typography>
                            <Chip 
                              label={job.status} 
                              color={getStatusColor(job.status) as any}
                              size="small"
                            />
                          </Box>
                        }
                        secondary={
                          <Box>
                            <Typography variant="body2" color="textSecondary">
                              Targets: {job.targets.join(', ')} | Type: {job.traffic_type}
                            </Typography>
                            <Typography variant="caption" color="textSecondary">
                              Created: {new Date(job.created_at).toLocaleString()}
                            </Typography>
                          </Box>
                        }
                      />
                      <ListItemSecondaryAction>
                        <Box display="flex" gap={1}>
                          <Button
                            size="small"
                            onClick={() => navigate(`/jobs/${job.job_id}`)}
                          >
                            Details
                          </Button>
                          {job.status === 'running' && (
                            <IconButton
                              size="small"
                              color="error"
                              onClick={() => handleStopJob(job.job_id)}
                              title="Stop job"
                            >
                              <StopIcon />
                            </IconButton>
                          )}
                        </Box>
                      </ListItemSecondaryAction>
                    </ListItem>
                  ))}
                </List>
              )}
            </CardContent>
          </Card>
        </Grid>
      </Grid>
    </Box>
  );
};

export default DashboardPage;