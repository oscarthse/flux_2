'use client';

import { createContext, useContext, useState, useEffect, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { api, User, LoginRequest, RegisterRequest } from '@/lib/api';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  login: (data: LoginRequest) => Promise<string | null>;
  register: (data: RegisterRequest) => Promise<string | null>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const router = useRouter();

  // Check for existing token on mount
  useEffect(() => {
    const checkAuth = async () => {
      const token = localStorage.getItem('access_token');
      if (token) {
        const { data, error } = await api.auth.me();
        if (data) {
          setUser(data);
        } else {
          // Token invalid, clear it
          localStorage.removeItem('access_token');
          localStorage.removeItem('refresh_token');
        }
      }
      setIsLoading(false);
    };

    checkAuth();
  }, []);

  const login = async (data: LoginRequest): Promise<string | null> => {
    const { data: tokens, error } = await api.auth.login(data);

    if (error) {
      return error;
    }

    if (tokens) {
      localStorage.setItem('access_token', tokens.access_token);
      localStorage.setItem('refresh_token', tokens.refresh_token);

      // Fetch user info
      const { data: userData } = await api.auth.me();
      if (userData) {
        setUser(userData);
      }

      router.push('/dashboard');
    }

    return null;
  };

  const register = async (data: RegisterRequest): Promise<string | null> => {
    const { data: tokens, error } = await api.auth.register(data);

    if (error) {
      return error;
    }

    if (tokens) {
      localStorage.setItem('access_token', tokens.access_token);
      localStorage.setItem('refresh_token', tokens.refresh_token);

      // Fetch user info
      const { data: userData } = await api.auth.me();
      if (userData) {
        setUser(userData);
      }

      router.push('/dashboard');
    }

    return null;
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
    router.push('/login');
  };

  return (
    <AuthContext.Provider value={{ user, isLoading, login, register, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
