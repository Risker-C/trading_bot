'use client';

import { useState, useEffect, useMemo } from 'react';
import { useBacktestStore } from '@/stores/useBacktestStore';
import { useWebSocketContext } from '@/context/WebSocketContext';
import { Card } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import KLineChart from '@/components/KLineChart';
import DatePicker from 'react-datepicker';
import 'react-datepicker/dist/react-datepicker.css';
import axios from 'axios';
import { StrategyMultiSelector } from '@/components/backtest/StrategyMultiSelector';
import { WeightConfigList } from '@/components/backtest/WeightConfigList';
import { WeightBalancePanel } from '@/components/backtest/WeightBalancePanel';

export default function BacktestPage() {
  const {
    params,
    setParams,
    currentSessionId,
    setCurrentSessionId,
    setStatus,
    activeTradeId,
    setActiveTradeId,
    status,
    addStrategy,
    removeStrategy,
    updateWeight,
    autoBalanceWeights
  } = useBacktestStore();
  const { data: wsData } = useWebSocketContext();
  const [loading, setLoading] = useState(false);
  const [metrics, setMetrics] = useState<any>(null);
  const [trades, setTrades] = useState<any[]>([]);
  const [klines, setKlines] = useState<any[]>([]);

  // 计算总权重和验证状态
  const totalWeight = useMemo(
    () => params.selectedStrategies.reduce((sum, s) => sum + s.weight, 0),
    [params.selectedStrategies]
  );

  const isWeightValid = useMemo(
    () => Math.abs(totalWeight - 100) < 0.01,
    [totalWeight]
  );

  const isMultiStrategy = params.selectedStrategies.length > 1;

  // 策略切换处理
  const handleStrategyToggle = (name: string) => {
    const isSelected = params.selectedStrategies.some(s => s.name === name);
    if (isSelected) {
      removeStrategy(name);
    } else {
      addStrategy(name);
    }
  };

  useEffect(() => {
    if (wsData.backtest && wsData.backtest.session_id === currentSessionId) {
      const backendStatus = wsData.backtest.status;
      if (backendStatus === 'completed' || backendStatus === 'failed') {
        setStatus('finished');
      } else if (backendStatus === 'created' || backendStatus === 'running') {
        setStatus('running');
      }
    }
  }, [wsData.backtest, currentSessionId, setStatus]);

  useEffect(() => {
    if (!currentSessionId || status === 'idle') return;

    const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    
    const fetchResults = async () => {
      try {
        const [metricsRes, tradesRes, klinesRes] = await Promise.all([
          axios.get(`${apiUrl}/api/backtests/sessions/${currentSessionId}/metrics`),
          axios.get(`${apiUrl}/api/backtests/sessions/${currentSessionId}/trades?limit=50`),
          axios.get(`${apiUrl}/api/backtests/sessions/${currentSessionId}/klines?limit=1000`)
        ]);

        if (metricsRes.data) {
          setMetrics(metricsRes.data);
          setTrades(tradesRes.data);
          setKlines(klinesRes.data);
          if (status === 'running') {
            setStatus('finished');
          }
        }
      } catch (error) {
        console.error('Failed to fetch results:', error);
      }
    };

    // 如果状态是 running，设置定时轮询
    let interval: NodeJS.Timeout | null = null;
    if (status === 'running') {
      fetchResults(); // 立即获取一次
      interval = setInterval(fetchResults, 5000);
    } else if (status === 'finished' && !metrics) {
      // 如果状态变成了 finished 但还没有获取到数据，再获取一次
      fetchResults();
    }

    return () => {
      if (interval) clearInterval(interval);
    };
  }, [currentSessionId, status, metrics, setStatus]);

  const handleStart = async () => {
    // 验证权重
    if (!isWeightValid) {
      alert('权重总和必须为 100%，当前为 ' + totalWeight.toFixed(1) + '%');
      return;
    }

    if (params.selectedStrategies.length === 0) {
      alert('请至少选择一个策略');
      return;
    }

    try {
      setLoading(true);
      setMetrics(null);
      setTrades([]);
      setKlines([]);
      const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

      // 构建请求参数
      const requestData: any = {
        symbol: params.symbol,
        timeframe: params.interval,
        start_ts: params.dateRange[0] ? Math.floor(params.dateRange[0].getTime() / 1000) : Math.floor(Date.now() / 1000) - 86400 * 30,
        end_ts: params.dateRange[1] ? Math.floor(params.dateRange[1].getTime() / 1000) : Math.floor(Date.now() / 1000),
        initial_capital: params.capital,
      };

      // 多策略模式
      if (isMultiStrategy) {
        requestData.strategy_name = 'weighted_composite';
        requestData.strategy_params = {
          strategies: params.selectedStrategies.map(s => ({
            name: s.name,
            weight: s.weight / 100, // 转换为 0-1
          })),
          threshold: 0.30,
        };
      } else {
        // 单策略模式
        requestData.strategy_name = params.selectedStrategies[0].name;
        requestData.strategy_params = params.strategyParams;
      }

      const response = await axios.post(`${apiUrl}/api/backtests/sessions`, requestData);

      setCurrentSessionId(response.data.session_id);

      await axios.post(`${apiUrl}/api/backtests/sessions/${response.data.session_id}/start`);
      setStatus('running');
    } catch (error) {
      console.error('Failed to start backtest:', error);
      alert('Failed to start backtest');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container mx-auto p-6">
      <h1 className="text-3xl font-bold mb-6">回测系统</h1>

      <Card className="p-6">
        <h2 className="text-xl font-semibold mb-4">回测配置</h2>

        <div className="space-y-4">
          <div>
            <Label htmlFor="symbol">交易对</Label>
            <Input
              id="symbol"
              value={params.symbol}
              onChange={(e) => setParams({ symbol: e.target.value })}
              placeholder="BTC/USDT:USDT"
            />
          </div>

          <div>
            <Label htmlFor="interval">时间周期</Label>
            <select
              id="interval"
              value={params.interval}
              onChange={(e) => setParams({ interval: e.target.value })}
              className="w-full p-2 border rounded"
            >
              <option value="1m">1分钟</option>
              <option value="5m">5分钟</option>
              <option value="15m">15分钟</option>
              <option value="30m">30分钟</option>
              <option value="1h">1小时</option>
              <option value="4h">4小时</option>
              <option value="1d">1天</option>
            </select>
          </div>

          <div>
            <Label htmlFor="capital">初始资金 (USDT)</Label>
            <Input
              id="capital"
              type="number"
              value={params.capital}
              onChange={(e) => setParams({ capital: parseFloat(e.target.value) })}
              placeholder="10000"
            />
          </div>

          <div>
            <Label>回测时间范围</Label>
            <div className="flex gap-2">
              <DatePicker
                selected={params.dateRange[0]}
                onChange={(date: Date | null) => setParams({ dateRange: [date, params.dateRange[1]] })}
                selectsStart
                startDate={params.dateRange[0]}
                endDate={params.dateRange[1]}
                placeholderText="开始日期"
                dateFormat="yyyy-MM-dd"
                className="w-full p-2 border rounded"
              />
              <DatePicker
                selected={params.dateRange[1]}
                onChange={(date: Date | null) => setParams({ dateRange: [params.dateRange[0], date] })}
                selectsEnd
                startDate={params.dateRange[0]}
                endDate={params.dateRange[1]}
                minDate={params.dateRange[0] || undefined}
                placeholderText="结束日期"
                dateFormat="yyyy-MM-dd"
                className="w-full p-2 border rounded"
              />
            </div>
            <p className="text-xs text-muted-foreground mt-1">留空则默认最近30天</p>
          </div>

          {/* 策略多选组件 */}
          <StrategyMultiSelector
            selected={params.selectedStrategies.map(s => s.name)}
            onToggle={handleStrategyToggle}
          />

          {/* 权重配置（仅多策略时显示） */}
          {isMultiStrategy && (
            <div className="space-y-3">
              <WeightConfigList
                strategies={params.selectedStrategies}
                onUpdateWeight={updateWeight}
                onRemove={removeStrategy}
              />
              <WeightBalancePanel
                strategies={params.selectedStrategies}
                onAutoBalance={autoBalanceWeights}
              />
            </div>
          )}

          <Button
            onClick={handleStart}
            disabled={loading || status === 'running' || !isWeightValid || params.selectedStrategies.length === 0}
            className="w-full"
          >
            {loading ? '启动中...' : status === 'running' ? '回测进行中...' : '开始回测'}
          </Button>
        </div>
      </Card>

      {status === 'running' && !metrics && (
        <Card className="mt-6 p-12 flex flex-col items-center justify-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mb-4"></div>
          <p className="text-lg font-medium">正在执行回测并生成报告...</p>
          <p className="text-sm text-muted-foreground mt-2">这可能需要几秒到几分钟的时间，请稍候。</p>
        </Card>
      )}

      {klines.length > 0 && (
        <Card className="mt-6 p-6">
          <h2 className="text-xl font-semibold mb-4">K线图表</h2>
          <KLineChart
            data={klines}
            trades={trades}
            activeTradeId={activeTradeId}
            onTradeClick={setActiveTradeId}
            strategyName={params.strategyName}
          />
        </Card>
      )}

      {metrics && (
        <div className="mt-6 space-y-6">
          <Card className="p-6">
            <div className="flex justify-between items-center mb-4">
              <h2 className="text-xl font-semibold">回测结果</h2>
              <Button
                onClick={() => {
                  const apiUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
                  window.open(`${apiUrl}/api/backtests/sessions/${currentSessionId}/export`, '_blank');
                }}
                variant="outline"
                size="sm"
              >
                导出报告
              </Button>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <p className="text-sm text-muted-foreground">总收益率</p>
                <p className={`text-2xl font-bold ${metrics.total_return >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {metrics.total_return.toFixed(2)}%
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">总盈亏</p>
                <p className={`text-2xl font-bold ${metrics.total_pnl >= 0 ? 'text-green-600 dark:text-green-400' : 'text-red-600 dark:text-red-400'}`}>
                  {metrics.total_pnl.toFixed(2)} USDT
                </p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">胜率</p>
                <p className="text-2xl font-bold">{(metrics.win_rate * 100).toFixed(1)}%</p>
              </div>
              <div>
                <p className="text-sm text-muted-foreground">交易次数</p>
                <p className="text-2xl font-bold">{metrics.total_trades}</p>
              </div>
            </div>
          </Card>

          <Card className="p-6">
            <h2 className="text-xl font-semibold mb-4">交易记录</h2>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b">
                    <th className="text-left p-2">交易对</th>
                    <th className="text-left p-2">时间</th>
                    <th className="text-left p-2">方向</th>
                    <th className="text-left p-2">操作</th>
                    <th className="text-right p-2">价格</th>
                    <th className="text-right p-2">数量</th>
                    <th className="text-right p-2">盈亏</th>
                    <th className="text-left p-2">策略</th>
                    <th className="text-left p-2">原因</th>
                  </tr>
                </thead>
                <tbody>
                  {trades.map((trade) => {
                    // 找到配对的交易
                    const pairedTrade = trade.action === 'close'
                      ? trades.find(t => t.id === trade.open_trade_id)
                      : trades.find(t => t.open_trade_id === trade.id && t.action === 'close');

                    const isPaired = activeTradeId === trade.id || activeTradeId === pairedTrade?.id;

                    return (
                      <tr
                        key={trade.id}
                        className={`border-b border-border cursor-pointer transition-colors ${
                          isPaired ? 'bg-blue-100 dark:bg-blue-900/30' : 'hover:bg-muted/50'
                        }`}
                        onClick={() => setActiveTradeId(trade.id)}
                      >
                        <td className="p-2">
                          {trade.action === 'close' && trade.open_trade_id && (
                            <span className="text-xs text-muted-foreground">
                              #{trade.open_trade_id} → #{trade.id}
                            </span>
                          )}
                          {trade.action === 'open' && pairedTrade && (
                            <span className="text-xs text-muted-foreground">
                              #{trade.id} → #{pairedTrade.id}
                            </span>
                          )}
                          {trade.action === 'open' && !pairedTrade && (
                            <span className="text-xs text-orange-500 dark:text-orange-400">
                              #{trade.id} (未平仓)
                            </span>
                          )}
                        </td>
                        <td className="p-2">{new Date(trade.ts * 1000).toLocaleString()}</td>
                        <td className="p-2">
                          <span className={`px-2 py-1 rounded text-xs ${
                            trade.side === 'long'
                              ? 'bg-green-100 dark:bg-green-900/30 text-green-800 dark:text-green-300'
                              : 'bg-red-100 dark:bg-red-900/30 text-red-800 dark:text-red-300'
                          }`}>
                            {trade.side}
                          </span>
                        </td>
                        <td className="p-2">
                          <span className={`px-2 py-1 rounded text-xs ${
                            trade.action === 'open'
                              ? 'bg-blue-100 dark:bg-blue-900/30 text-blue-800 dark:text-blue-300'
                              : 'bg-muted text-muted-foreground'
                          }`}>
                            {trade.action === 'open' ? '开仓' : '平仓'}
                          </span>
                        </td>
                        <td className="p-2 text-right">{trade.price.toFixed(2)}</td>
                        <td className="p-2 text-right">{trade.qty.toFixed(4)}</td>
                        <td className={`p-2 text-right ${
                          trade.pnl >= 0
                            ? 'text-green-600 dark:text-green-400'
                            : 'text-red-600 dark:text-red-400'
                        }`}>
                          {trade.pnl ? trade.pnl.toFixed(2) : '-'}
                        </td>
                        <td className="p-2 text-xs">{trade.strategy_name}</td>
                        <td className="p-2 text-xs text-muted-foreground">{trade.reason || '-'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </Card>
        </div>
      )}
    </div>
  );
}
