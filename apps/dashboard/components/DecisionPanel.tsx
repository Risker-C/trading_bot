'use client';

import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Progress } from '@/components/ui/progress';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { DecisionData } from '@/lib/types/decision';
import { AlertCircle, TrendingUp, TrendingDown, Clock, CheckCircle, XCircle } from 'lucide-react';
import { useEffect, useState } from 'react';

interface DecisionPanelProps {
  decision?: DecisionData;
}

const formatTime = (seconds: number) => {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const getSignalColor = (strength: number) => {
  if (strength < 0.3) return 'text-trading-down';
  if (strength < 0.7) return 'text-yellow-500';
  return 'text-trading-up';
};

const getSignalBadgeVariant = (type: string): 'default' | 'destructive' | 'secondary' => {
  if (type === 'long') return 'default';
  if (type === 'short') return 'destructive';
  return 'secondary';
};

export function DecisionPanel({ decision }: DecisionPanelProps) {
  const [countdown, setCountdown] = useState(0);

  useEffect(() => {
    if (decision?.risk_status?.cooldown_remaining) {
      setCountdown(decision.risk_status.cooldown_remaining);
      const timer = setInterval(() => {
        setCountdown(prev => Math.max(0, prev - 1));
      }, 1000);
      return () => clearInterval(timer);
    }
  }, [decision?.risk_status?.cooldown_remaining]);

  if (!decision) {
    return (
      <Card className="p-6">
        <div className="text-center text-muted-foreground">
          <AlertCircle className="h-12 w-12 mx-auto mb-2 opacity-50" />
          <p>等待决策数据...</p>
        </div>
      </Card>
    );
  }

  return (
    <Card className="p-6">
      <h2 className="text-lg font-semibold mb-4">决策信息</h2>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* 信号强度区 */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">信号强度</span>
            <span className={`text-lg font-bold font-mono tabular-nums ${getSignalColor(decision.signal_strength)}`}>
              {(decision.signal_strength * 100).toFixed(1)}%
            </span>
          </div>
          <Progress value={decision.signal_strength * 100} className="h-2" aria-label="信号强度" />

          <div className="flex items-center justify-between mt-2">
            <span className="text-sm font-medium">信号类型</span>
            <Badge variant={getSignalBadgeVariant(decision.signal_type)}>
              {decision.signal_type === 'long' ? '做多' : decision.signal_type === 'short' ? '做空' : '持有'}
            </Badge>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">信号置信度</span>
            <span className="text-sm font-mono tabular-nums">{(decision.signal_confidence * 100).toFixed(1)}%</span>
          </div>
        </div>

        {/* 市场状态区 */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">市场状态</span>
            <span className="text-sm font-semibold">{decision.market_state}</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">ADX指标</span>
            <span className="text-sm font-mono tabular-nums">{decision.market_adx.toFixed(1)}</span>
          </div>

          <div className="flex items-center justify-between">
            <span className="text-sm font-medium">订单建议</span>
            <Badge variant={getSignalBadgeVariant(decision.order_suggestion)}>
              {decision.order_suggestion === 'long' ? '买入' : decision.order_suggestion === 'short' ? '卖出' : '持有'}
            </Badge>
          </div>
        </div>
      </div>

      {/* 风控状态区 */}
      <div className="mt-6 p-4 bg-muted/50 rounded-lg">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium">风控状态</span>
          {decision.risk_status.can_trade ? (
            <CheckCircle className="h-5 w-5 text-trading-up" />
          ) : (
            <XCircle className="h-5 w-5 text-trading-down" />
          )}
        </div>
        <p className="text-sm text-muted-foreground">{decision.risk_status.reason}</p>

        {countdown > 0 && (
          <div className="flex items-center gap-2 mt-2 text-sm">
            <Clock className="h-4 w-4" />
            <span>冷却剩余: {formatTime(countdown)}</span>
          </div>
        )}
      </div>

      {/* 阻塞原因警告 */}
      {decision.blocking_reasons.length > 0 && (
        <Alert className="mt-4" variant="destructive">
          <AlertCircle className="h-4 w-4" />
          <AlertDescription>
            <div className="font-semibold mb-1">交易被阻止:</div>
            <ul className="list-disc list-inside space-y-1">
              {decision.blocking_reasons.map((reason, idx) => (
                <li key={idx} className="text-sm">{reason}</li>
              ))}
            </ul>
          </AlertDescription>
        </Alert>
      )}

      {/* 决策链 */}
      {decision.logic_chain.length > 0 && (
        <Accordion type="single" collapsible className="mt-4">
          <AccordionItem value="logic-chain">
            <AccordionTrigger>查看决策链</AccordionTrigger>
            <AccordionContent>
              <div className="space-y-2">
                {decision.logic_chain.map((step, idx) => (
                  <div key={idx} className="flex items-center gap-3 p-2 bg-muted/30 rounded">
                    {step.passed ? (
                      <CheckCircle className="h-4 w-4 text-trading-up flex-shrink-0" />
                    ) : (
                      <XCircle className="h-4 w-4 text-trading-down flex-shrink-0" />
                    )}
                    <div className="flex-1">
                      <div className="text-sm font-medium">{step.step}</div>
                      <div className="text-xs text-muted-foreground">{step.result}</div>
                    </div>
                  </div>
                ))}
              </div>
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      )}
    </Card>
  );
}
