import type { LucideIcon } from 'lucide-react';

export type TrendDirection = 'up' | 'down' | 'neutral';

export type SemanticTone = 'profit' | 'loss' | 'neutral';

export interface ThemeTone {
  foreground: string;
  softBg: string;
  border: string;
}

export interface DashboardThemeTokens {
  tone: Record<SemanticTone, ThemeTone>;
  card: {
    gradientFrom: string;
    gradientTo: string;
    border: string;
    shadow: string;
  };
  typography: {
    numericFont: string;
  };
}

export interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  trend?: number;
  trendDirection?: TrendDirection;
  className?: string;
}

export interface ChartPoint {
  timestamp: string;
  value: number;
}

export interface ChartTooltipPayloadItem {
  name: string;
  value: number;
  color?: string;
}

export interface ChartTooltipProps {
  label?: string;
  payload?: ChartTooltipPayloadItem[];
}

export interface GradientAreaChartProps {
  data: ChartPoint[];
  xKey: 'timestamp';
  yKey: 'value';
  gradientId: string;
  height?: number;
  className?: string;
}
