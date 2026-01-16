'use client';

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useState } from 'react';
import { usePathname, useRouter } from 'next/navigation';
import { AuthProvider, useAuth } from '@/context/AuthContext';
import { WebSocketProvider } from '@/context/WebSocketContext';
import { FullPageLoader } from '@/components/FullPageLoader';

function AuthGuard({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isInitializing } = useAuth();
  const pathname = usePathname();
  const router = useRouter();

  if (isInitializing) {
    return <FullPageLoader />;
  }

  if (!isAuthenticated && pathname !== '/login') {
    router.replace('/login');
    return <FullPageLoader />;
  }

  return <>{children}</>;
}

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
            refetchOnMount: false,
          },
        },
      })
  );

  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <AuthGuard>
          <WebSocketProvider>
            {children}
          </WebSocketProvider>
        </AuthGuard>
      </AuthProvider>
    </QueryClientProvider>
  );
}
