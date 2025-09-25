import React from 'react';
import { Chip, Tooltip } from '@mui/material';
import { 
  WifiOff as DisconnectedIcon,
  Wifi as ConnectedIcon,
  HourglassEmpty as ConnectingIcon 
} from '@mui/icons-material';

interface ConnectionStatusProps {
  connected: boolean;
  connecting: boolean;
  error: string | null;
}

const ConnectionStatus: React.FC<ConnectionStatusProps> = ({ 
  connected, 
  connecting, 
  error 
}) => {
  const getStatus = () => {
    if (connecting) {
      return {
        label: 'Connecting...',
        color: 'warning' as const,
        icon: <ConnectingIcon />,
      };
    }
    
    if (connected) {
      return {
        label: 'Connected',
        color: 'success' as const,
        icon: <ConnectedIcon />,
      };
    }
    
    return {
      label: 'Disconnected',
      color: 'error' as const,
      icon: <DisconnectedIcon />,
    };
  };

  const status = getStatus();
  const tooltipTitle = error ? `Connection error: ${error}` : status.label;

  return (
    <div className="connection-status">
      <Tooltip title={tooltipTitle} arrow>
        <Chip
          icon={status.icon}
          label={status.label}
          color={status.color}
          variant="filled"
          size="small"
        />
      </Tooltip>
    </div>
  );
};

export default ConnectionStatus;