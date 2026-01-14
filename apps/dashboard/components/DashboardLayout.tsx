'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { LayoutDashboard, TrendingUp, BarChart3, Activity } from 'lucide-react';
import { ThemeToggle } from './theme-toggle';
import { TickerDisplay } from './TickerDisplay';
import { useWebSocket } from '@/hooks/useWebSocket';

const navItems = [
  { href: '/', label: 'Dashboard', icon: LayoutDashboard },
  { href: '/trades', label: 'Trades', icon: TrendingUp },
  { href: '/analytics', label: 'Analytics', icon: BarChart3 },
  { href: '/monitor', label: 'Monitor', icon: Activity },
];

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { data } = useWebSocket(['ticker']);

  return (
    <div className="flex h-screen bg-background">
      <aside className="w-64 border-r bg-card/50 hidden md:block">
        <div className="p-6">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-primary to-primary/60 bg-clip-text text-transparent">
            Trading Bot
          </h1>
        </div>
        <nav className="px-4 space-y-2">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = pathname === item.href;
            return (
              <Link
                key={item.href}
                href={item.href}
                className={`flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-300 ${
                  isActive
                    ? 'bg-primary text-primary-foreground shadow-md'
                    : 'hover:bg-accent text-muted-foreground hover:text-foreground'
                }`}
              >
                <Icon className="h-5 w-5" />
                <span className="font-medium">{item.label}</span>
              </Link>
            );
          })}
        </nav>
      </aside>

      <div className="flex-1 flex flex-col overflow-hidden">
        <header className="border-b bg-card/50 px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <h2 className="text-xl font-semibold md:hidden">Trading Bot</h2>
              <div className="hidden md:block">
                <TickerDisplay ticker={data.ticker} />
              </div>
            </div>
            <div className="flex items-center gap-4">
              <ThemeToggle />
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-primary to-primary/60" />
            </div>
          </div>
        </header>

        <main className="flex-1 overflow-auto p-6">
          {children}
        </main>
      </div>
    </div>
  );
}
