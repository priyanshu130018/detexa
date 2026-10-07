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
  const [token, setToken] = useState<string | null>(localStorage.getItem('detexa_token'));
  const [user, setUser] = useState<{ userId: string; name: string; email: string; isAdmin: boolean } | null>(() => {
    const saved = localStorage.getItem('detexa_user');
    return saved ? JSON.parse(saved) : null;
  });
  const [isLoading, setIsLoading] = useState<boolean>(true);

  useEffect(() => {
    const checkAuth = async () => {
      if (token) {
        try {
          const profile = await authService.getMe();
          setUser({
            userId: profile.id,
            name: profile.name,
            email: profile.email,
            isAdmin: profile.is_admin,
          });
        } catch (err) {
          logout();
        }
      }
      setIsLoading(false);
    };
    checkAuth();
  }, [token]);

  const saveAuth = (data: TokenResponse) => {
    setToken(data.access_token);
    const userInfo = {
      userId: data.user_id,
      name: data.name,
      email: data.email,
      isAdmin: data.is_admin,
    };
    setUser(userInfo);
    localStorage.setItem('detexa_token', data.access_token);
    localStorage.setItem('detexa_user', JSON.stringify(userInfo));
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
