export interface DecisionData {
  signal_strength: number;
  signal_confidence: number;
  signal_type: 'hold' | 'long' | 'short';
  market_state: string;
  market_adx: number;
  risk_status: {
    can_trade: boolean;
    reason: string;
    cooldown_remaining: number;
  };
  drawdown_status: {
    allowed: boolean;
    current_drawdown_pct: number;
  };
  execution_filters: Record<string, any>;
  blocking_reasons: string[];
  order_suggestion: string;
  logic_chain: Array<{
    step: string;
    result: string;
    passed: boolean;
  }>;
  updated_at: string;
}
