import React, { createContext, useContext, useState, useEffect } from 'react';
import { TokenResponse } from '../types';
import { authService } from '../services/auth.service';

interface AuthContextType {
  token: string | null;
  user: {
    userId: string;
    name: string;
    email: string;
    isAdmin: boolean;
  } | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  login: (email: string, pass: string) => Promise<void>;
  register: (name: string, email: string, mobile?: string, pass?: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [token, setToken] = useState<string | null>(() => localStorage.getItem('detexa_token'));
  const [user, setUser] = useState<{ userId: string; name: string; email: string; isAdmin: boolean } | null>(() => {
    const saved = localStorage.getItem('detexa_user');
    if (saved) {
      try {
        return JSON.parse(saved);
      } catch {
        return null;
      }
    }
    return null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(() => {
    // Only block with loading if we have a token but haven't populated user data from localStorage yet
    return !!localStorage.getItem('detexa_token') && !localStorage.getItem('detexa_user');
  });

  // Verify stored session on initial application mount only
  useEffect(() => {
    const initAuth = async () => {
      const storedToken = localStorage.getItem('detexa_token');
      if (storedToken) {
        try {
          // If we already have saved user info, don't block render; verify in background
          const profile = await authService.getMe();
          const userInfo = {
            userId: profile.id,
            name: profile.name,
            email: profile.email,
            isAdmin: profile.is_admin,
          };
          setUser(userInfo);
          localStorage.setItem('detexa_user', JSON.stringify(userInfo));
        } catch (err: any) {
          if (err.response?.status === 401 || err.response?.status === 403) {
            logout();
          }
        }
      }
      setIsLoading(false);
    };

    initAuth();
  }, []);

  const saveAuth = (data: TokenResponse) => {
    const userInfo = {
      userId: data.user_id,
      name: data.name,
      email: data.email,
      isAdmin: data.is_admin,
    };
    localStorage.setItem('detexa_token', data.access_token);
    localStorage.setItem('detexa_user', JSON.stringify(userInfo));
    setToken(data.access_token);
    setUser(userInfo);
    setIsLoading(false);
  };

  const login = async (email: string, pass: string) => {
    const data = await authService.login(email, pass);
    saveAuth(data);
  };

  const register = async (name: string, email: string, mobile?: string, pass?: string) => {
    const data = await authService.register(name, email, mobile, pass);
    saveAuth(data);
  };

  const logout = () => {
    setToken(null);
    setUser(null);
    setIsLoading(false);
    localStorage.removeItem('detexa_token');
    localStorage.removeItem('detexa_user');
  };

  return (
    <AuthContext.Provider
      value={{
        token,
        user,
        isAuthenticated: !!token,
        isLoading,
        login,
        register,
        logout,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};
