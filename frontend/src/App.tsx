import React from 'react';
import { Routes, Route, Navigate } from 'react-router-dom';
import { Box } from '@mui/material';
import { useAuth } from './contexts/AuthContext';
import { useWebSocket } from './contexts/WebSocketContext';

// Components (will create these next)
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import JobsPage from './pages/JobsPage';
import JobDetailPage from './pages/JobDetailPage';
import CreateJobPage from './pages/CreateJobPage';
import AdminPage from './pages/AdminPage';
import Layout from './components/Layout';
import LoadingSpinner from './components/LoadingSpinner';
import ConnectionStatus from './components/ConnectionStatus';

const App: React.FC = () => {
  const { isAuthenticated, loading } = useAuth();
  const { connected, connecting, error } = useWebSocket();

  if (loading) {
    return (
      <Box
        display="flex"
        justifyContent="center"
        alignItems="center"
        minHeight="100vh"
      >
        <LoadingSpinner />
      </Box>
    );
  }

  return (
    <>
      <ConnectionStatus 
        connected={connected} 
        connecting={connecting} 
        error={error} 
      />
      
      <Routes>
        {!isAuthenticated ? (
          <>
            <Route path="/login" element={<LoginPage />} />
            <Route path="*" element={<Navigate to="/login" replace />} />
          </>
        ) : (
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/dashboard" replace />} />
            <Route path="dashboard" element={<DashboardPage />} />
            <Route path="jobs" element={<JobsPage />} />
            <Route path="jobs/create" element={<CreateJobPage />} />
            <Route path="jobs/:jobId" element={<JobDetailPage />} />
            <Route path="admin" element={<AdminPage />} />
            <Route path="*" element={<Navigate to="/dashboard" replace />} />
          </Route>
        )}
      </Routes>
    </>
  );
};

export default App;