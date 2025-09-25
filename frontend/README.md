# Hping3 Traffic Orchestrator - Frontend

React-based web interface for the Hping3 Traffic Orchestrator platform.

## Features

- **Authentication**: Secure login with JWT token management
- **Real-time Updates**: WebSocket integration for live job monitoring
- **Job Management**: Create, monitor, and control traffic generation jobs
- **Dashboard**: System overview with statistics and recent activity
- **Responsive Design**: Works on desktop and mobile devices
- **Role-based Access**: Different interfaces for admin, operator, and read-only users

## Technology Stack

- **React 18** with TypeScript
- **Material-UI (MUI)** for components and styling
- **React Router** for navigation
- **React Query** for API state management
- **WebSocket** for real-time updates
- **Axios** for HTTP requests

## Quick Start

### Prerequisites

- Node.js 16+ and npm
- Running backend API server (see main README)

### Installation

```bash
# Navigate to frontend directory
cd frontend

# Install dependencies
npm install

# Start development server
npm start
```

The application will be available at `http://localhost:3000`.

### Build for Production

```bash
# Create production build
npm run build

# Serve built files (requires a web server)
npx serve -s build
```

## Development

### Project Structure

```
src/
├── components/          # Reusable UI components
├── contexts/           # React contexts (Auth, WebSocket)
├── pages/              # Page components
├── services/           # API service layer
├── types/              # TypeScript type definitions
├── App.tsx             # Main app component
├── index.tsx           # Application entry point
└── theme.ts            # Material-UI theme configuration
```

### Environment Variables

Configure the API endpoint in `.env.development`:

```bash
REACT_APP_API_URL=http://localhost:8000/api/v1
REACT_APP_WS_URL=ws://localhost:8000/api/v1/ws
```

### Available Scripts

- `npm start` - Start development server
- `npm build` - Build for production
- `npm test` - Run tests
- `npm run lint` - Run ESLint
- `npm run lint:fix` - Fix ESLint errors

## Usage

### Default Login

- **Username**: admin
- **Password**: admin123

### Navigation

- **Dashboard**: System overview and recent jobs
- **Jobs**: Job management and listing
- **Create Job**: Create new traffic generation jobs
- **Admin**: System administration (admin users only)

### Real-time Features

The interface automatically updates when:
- Job status changes
- New jobs are created
- System events occur
- Other users perform actions

### Job Creation

1. Navigate to "Create Job"
2. Enter job name and target IPs
3. Select traffic type (ICMP, TCP, UDP)
4. Configure parameters (PPS, duration, ports)
5. Choose priority level
6. Enable "Dry Run" for testing
7. Click "Create Job"

## API Integration

The frontend communicates with the backend via:

- **REST API**: Job management, authentication, configuration
- **WebSocket**: Real-time updates and notifications

Authentication uses JWT tokens stored in localStorage with automatic refresh.

## Security Features

- JWT token-based authentication
- Automatic token refresh
- Role-based access control
- Secure WebSocket connections
- Input validation and sanitization

## Browser Compatibility

- Chrome 88+
- Firefox 85+
- Safari 14+
- Edge 88+

## Troubleshooting

### Connection Issues

1. Verify backend API is running on correct port
2. Check CORS settings in backend configuration
3. Ensure WebSocket endpoint is accessible
4. Check browser console for errors

### Build Issues

```bash
# Clear node_modules and reinstall
rm -rf node_modules package-lock.json
npm install

# Clear build cache
npm run build -- --no-cache
```

### Development Tips

- Use browser dev tools to monitor WebSocket connections
- Check Network tab for API request/response details
- Enable React Developer Tools for component inspection
- Monitor console for authentication and API errors

## Contributing

1. Follow existing code style and structure
2. Add TypeScript types for new features
3. Include error handling for API calls
4. Test WebSocket functionality
5. Update this README for new features

## Future Enhancements

- Job templates and saved configurations
- Advanced filtering and search
- Export job results and reports
- Bulk job operations
- System health monitoring
- User preference settings
- Dark mode theme