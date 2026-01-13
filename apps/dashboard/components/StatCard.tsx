'use client';

import { LucideIcon } from 'lucide-react';
import { Card } from './ui/card';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: number;
  className?: string;
}

export function StatCard({ title, value, icon: Icon, trend, className = '' }: StatCardProps) {
  const trendColor = trend && trend > 0 ? 'text-green-500' : trend && trend < 0 ? 'text-red-500' : 'text-gray-500';

  return (
    <Card className={`p-6 bg-gradient-to-br from-background to-muted/20 hover:shadow-lg transition-all duration-300 ${className}`}>
      <div className="flex items-center justify-between">
        <div className="flex-1">
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-2">{value}</p>
          {trend !== undefined && (
            <p className={`text-sm mt-1 ${trendColor}`}>
              {trend > 0 ? '↑' : trend < 0 ? '↓' : '→'} {Math.abs(trend)}%
            </p>
          )}
        </div>
        <div className="ml-4">
          <div className="p-3 bg-primary/10 rounded-lg">
            <Icon className="h-6 w-6 text-primary" />
          </div>
        </div>
      </div>
    </Card>
  );
}
