import apiClient from './api';
import { AuthToken, User } from '../types/auth';

export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user: User;
}

export class AuthService {
  static async login(credentials: LoginRequest): Promise<LoginResponse> {
    const formData = new FormData();
    formData.append('username', credentials.username);
    formData.append('password', credentials.password);

    const response = await apiClient.client.post<AuthToken>('/auth/login', formData, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
    });

    // Get user profile after successful login
    const token = response.data.access_token;
    apiClient.setAuthToken(token);
    
    const userResponse = await apiClient.get<User>('/auth/me');

    return {
      access_token: token,
      token_type: response.data.token_type,
      user: userResponse.data,
    };
  }

  static async logout(): Promise<void> {
    try {
      await apiClient.post('/auth/logout');
    } catch (error) {
      // Ignore errors on logout
      console.warn('Logout request failed:', error);
    } finally {
      // Always clear local storage
      localStorage.removeItem('auth_token');
      localStorage.removeItem('user_data');
      apiClient.clearAuthToken();
    }
  }

  static async getCurrentUser(): Promise<User> {
    const response = await apiClient.get<User>('/auth/me');
    return response.data;
  }

  static async refreshToken(): Promise<AuthToken> {
    const response = await apiClient.post<AuthToken>('/auth/refresh');
    return response.data;
  }

  static async changePassword(oldPassword: string, newPassword: string): Promise<void> {
    await apiClient.post('/auth/change-password', {
      old_password: oldPassword,
      new_password: newPassword,
    });
  }

  static getStoredToken(): string | null {
    return localStorage.getItem('auth_token');
  }

  static getStoredUser(): User | null {
    const userData = localStorage.getItem('user_data');
    return userData ? JSON.parse(userData) : null;
  }

  static storeAuth(token: string, user: User): void {
    localStorage.setItem('auth_token', token);
    localStorage.setItem('user_data', JSON.stringify(user));
    apiClient.setAuthToken(token);
  }

  static clearAuth(): void {
    localStorage.removeItem('auth_token');
    localStorage.removeItem('user_data');
    apiClient.clearAuthToken();
  }
}

export default AuthService;