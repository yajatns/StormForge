import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Box,
  Typography,
  Card,
  CardContent,
  TextField,
  Button,
  FormControl,
  InputLabel,
  Select,
  MenuItem,
  Chip,
  Grid,
  Alert,
  Switch,
  FormControlLabel,
} from '@mui/material';
import { Save as SaveIcon, Cancel as CancelIcon } from '@mui/icons-material';
import { JobCreateRequest, TrafficType, Priority } from '../types/job';
import JobService from '../services/jobs';
import LoadingSpinner from '../components/LoadingSpinner';

const CreateJobPage: React.FC = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [formData, setFormData] = useState<JobCreateRequest>({
    name: '',
    targets: [],
    traffic_type: 'icmp',
    pps: 1,
    dry_run: true,
    priority: 'normal',
  });
  const [targetInput, setTargetInput] = useState('');

  const handleInputChange = (field: keyof JobCreateRequest, value: any) => {
    setFormData(prev => ({
      ...prev,
      [field]: value,
    }));
  };

  const handleAddTarget = () => {
    const target = targetInput.trim();
    if (target && !formData.targets.includes(target)) {
      handleInputChange('targets', [...formData.targets, target]);
      setTargetInput('');
    }
  };

  const handleRemoveTarget = (target: string) => {
    handleInputChange('targets', formData.targets.filter(t => t !== target));
  };

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    
    if (formData.targets.length === 0) {
      setError('At least one target is required');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      
      const job = await JobService.createJob(formData);
      navigate(`/jobs/${job.job_id}`);
    } catch (error: any) {
      console.error('Failed to create job:', error);
      setError(error.response?.data?.detail || 'Failed to create job');
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return <LoadingSpinner message="Creating job..." />;
  }

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Create Job
        </Typography>
        <Button
          variant="outlined"
          startIcon={<CancelIcon />}
          onClick={() => navigate('/jobs')}
        >
          Cancel
        </Button>
      </Box>

      {error && (
        <Alert severity="error" sx={{ mb: 3 }} onClose={() => setError(null)}>
          {error}
        </Alert>
      )}

      <Card>
        <CardContent>
          <Box component="form" onSubmit={handleSubmit}>
            <Grid container spacing={3}>
              <Grid item xs={12}>
                <TextField
                  fullWidth
                  label="Job Name"
                  value={formData.name}
                  onChange={(e) => handleInputChange('name', e.target.value)}
                  required
                />
              </Grid>

              <Grid item xs={12}>
                <Box>
                  <TextField
                    fullWidth
                    label="Target IP/Hostname"
                    value={targetInput}
                    onChange={(e) => setTargetInput(e.target.value)}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault();
                        handleAddTarget();
                      }
                    }}
                    helperText="Press Enter to add target"
                  />
                  <Box mt={2}>
                    {formData.targets.map((target) => (
                      <Chip
                        key={target}
                        label={target}
                        onDelete={() => handleRemoveTarget(target)}
                        sx={{ mr: 1, mb: 1 }}
                      />
                    ))}
                  </Box>
                </Box>
              </Grid>

              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Traffic Type</InputLabel>
                  <Select
                    value={formData.traffic_type}
                    label="Traffic Type"
                    onChange={(e) => handleInputChange('traffic_type', e.target.value)}
                  >
                    <MenuItem value="icmp">ICMP</MenuItem>
                    <MenuItem value="tcp-syn">TCP SYN</MenuItem>
                    <MenuItem value="tcp-ack">TCP ACK</MenuItem>
                    <MenuItem value="tcp-rst">TCP RST</MenuItem>
                    <MenuItem value="udp">UDP</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Packets per Second"
                  type="number"
                  value={formData.pps}
                  onChange={(e) => handleInputChange('pps', parseInt(e.target.value) || 1)}
                  inputProps={{ min: 1, max: 10000 }}
                />
              </Grid>

              {(formData.traffic_type === 'tcp-syn' || 
                formData.traffic_type === 'tcp-ack' || 
                formData.traffic_type === 'tcp-rst' ||
                formData.traffic_type === 'udp') && (
                <Grid item xs={12} md={6}>
                  <TextField
                    fullWidth
                    label="Destination Port"
                    type="number"
                    value={formData.dst_port || ''}
                    onChange={(e) => handleInputChange('dst_port', parseInt(e.target.value) || undefined)}
                    inputProps={{ min: 1, max: 65535 }}
                  />
                </Grid>
              )}

              <Grid item xs={12} md={6}>
                <TextField
                  fullWidth
                  label="Duration (seconds)"
                  type="number"
                  value={formData.duration || ''}
                  onChange={(e) => handleInputChange('duration', parseInt(e.target.value) || undefined)}
                  inputProps={{ min: 1 }}
                  helperText="Leave empty for continuous"
                />
              </Grid>

              <Grid item xs={12} md={6}>
                <FormControl fullWidth>
                  <InputLabel>Priority</InputLabel>
                  <Select
                    value={formData.priority}
                    label="Priority"
                    onChange={(e) => handleInputChange('priority', e.target.value)}
                  >
                    <MenuItem value="low">Low</MenuItem>
                    <MenuItem value="normal">Normal</MenuItem>
                    <MenuItem value="high">High</MenuItem>
                  </Select>
                </FormControl>
              </Grid>

              <Grid item xs={12}>
                <FormControlLabel
                  control={
                    <Switch
                      checked={formData.dry_run || false}
                      onChange={(e) => handleInputChange('dry_run', e.target.checked)}
                    />
                  }
                  label="Dry Run (test only, don't send actual traffic)"
                />
              </Grid>

              <Grid item xs={12}>
                <Box display="flex" gap={2} justifyContent="end">
                  <Button
                    variant="outlined"
                    onClick={() => navigate('/jobs')}
                  >
                    Cancel
                  </Button>
                  <Button
                    type="submit"
                    variant="contained"
                    startIcon={<SaveIcon />}
                    disabled={!formData.name || formData.targets.length === 0}
                  >
                    Create Job
                  </Button>
                </Box>
              </Grid>
            </Grid>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default CreateJobPage;