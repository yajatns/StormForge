import React from 'react';
import { Box, Typography, Button, Card, CardContent } from '@mui/material';
import { Add as AddIcon } from '@mui/icons-material';
import { useNavigate } from 'react-router-dom';

const JobsPage: React.FC = () => {
  const navigate = useNavigate();

  return (
    <Box>
      <Box display="flex" justifyContent="space-between" alignItems="center" mb={3}>
        <Typography variant="h4" component="h1">
          Jobs
        </Typography>
        <Button
          variant="contained"
          startIcon={<AddIcon />}
          onClick={() => navigate('/jobs/create')}
        >
          Create Job
        </Button>
      </Box>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Job Management
          </Typography>
          <Typography color="textSecondary">
            Advanced job listing and management interface will be implemented here.
            This will include filtering, sorting, bulk operations, and real-time job monitoring.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default JobsPage;