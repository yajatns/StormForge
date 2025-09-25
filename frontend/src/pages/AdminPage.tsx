import React from 'react';
import { Box, Typography, Card, CardContent } from '@mui/material';
import { useAuth } from '../contexts/AuthContext';

const AdminPage: React.FC = () => {
  const { user } = useAuth();

  if (user?.role !== 'admin') {
    return (
      <Box>
        <Typography variant="h4" component="h1" mb={3}>
          Access Denied
        </Typography>
        <Card>
          <CardContent>
            <Typography color="error">
              You do not have permission to access this page.
            </Typography>
          </CardContent>
        </Card>
      </Box>
    );
  }

  return (
    <Box>
      <Typography variant="h4" component="h1" mb={3}>
        Administration
      </Typography>

      <Card>
        <CardContent>
          <Typography variant="h6" gutterBottom>
            System Administration
          </Typography>
          <Typography color="textSecondary">
            Admin interface with user management, system settings, audit logs,
            security policies, and system monitoring will be implemented here.
          </Typography>
        </CardContent>
      </Card>
    </Box>
  );
};

export default AdminPage;