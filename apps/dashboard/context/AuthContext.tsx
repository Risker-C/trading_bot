'use client';

import { createContext, useContext, useEffect, useState, useCallback, ReactNode } from 'react';
import { useRouter } from 'next/navigation';

interface AuthContextType {
  isAuthenticated: boolean;
  isInitializing: boolean;
  token: string | null;
  requireAuth: () => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [isInitializing, setIsInitializing] = useState(true);
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [token, setToken] = useState<string | null>(null);

  useEffect(() => {
    const storedToken = typeof window !== 'undefined' ? localStorage.getItem('access_token') : null;

    if (storedToken) {
      setToken(storedToken);
      setIsAuthenticated(true);
    }

    setIsInitializing(false);
  }, []);

  const requireAuth = useCallback(() => {
    if (!isAuthenticated && !isInitializing) {
      router.replace('/login');
    }
  }, [isAuthenticated, isInitializing, router]);

  const logout = useCallback(() => {
    localStorage.removeItem('access_token');
    setToken(null);
    setIsAuthenticated(false);
    router.replace('/login');
  }, [router]);

  useEffect(() => {
    const handleStorageChange = (e: StorageEvent) => {
      if (e.key === 'access_token') {
        if (e.newValue) {
          setToken(e.newValue);
          setIsAuthenticated(true);
        } else {
          setToken(null);
          setIsAuthenticated(false);
          router.replace('/login');
        }
      }
    };

    window.addEventListener('storage', handleStorageChange);
    return () => window.removeEventListener('storage', handleStorageChange);
  }, [router]);

  return (
    <AuthContext.Provider value={{ isAuthenticated, isInitializing, token, requireAuth, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
}
