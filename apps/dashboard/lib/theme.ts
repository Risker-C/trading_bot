export const THEME_TONES = {
  profit: {
    foreground: 'text-trading-up',
    softBg: 'bg-trading-up/10',
    border: 'border-trading-up/20',
  },
  loss: {
    foreground: 'text-trading-down',
    softBg: 'bg-trading-down/10',
    border: 'border-trading-down/20',
  },
  neutral: {
    foreground: 'text-muted-foreground',
    softBg: 'bg-muted/10',
    border: 'border-muted/20',
  },
} as const;

export const CARD_STYLES = {
  gradientFrom: 'from-background',
  gradientTo: 'to-muted/20',
  border: 'border-border/50',
  shadow: 'shadow-soft-xl',
} as const;

export const NUMERIC_FONT = 'font-mono tabular-nums';
