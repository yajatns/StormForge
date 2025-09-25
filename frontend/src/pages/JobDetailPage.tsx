import React from 'react';
import { useParams } from 'react-router-dom';
import { Box, Typography, Card, CardContent } from '@mui/material';

const JobDetailPage: React.FC = () => {
  const { jobId } = useParams<{ jobId: string }>();

  return (
    <Box>
      <Typography variant="h4" component="h1" mb={3}>
        Job Details
      </Typography>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            Job ID: {jobId}
          </Typography>
          <Typography color="textSecondary">
            Detailed job view with real-time monitoring, output logs, metrics charts,
            and control actions will be implemented here.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default JobDetailPage;