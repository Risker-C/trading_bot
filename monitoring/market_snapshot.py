"""
市场快照工具 - 多时间周期市场数据查看
Phase 2 功能：结构化市场监控
"""
import asyncio
import json
from datetime import datetime
from typing import Dict, List, Optional
import pandas as pd

from config.settings import settings as config
from core.trader import BitgetTrader
from strategies.indicators import IndicatorCalculator
from strategies.market_regime import MarketRegimeDetector
from strategies.strategies import analyze_all_strategies, get_consensus_signal
from utils.logger_utils import get_logger

logger = get_logger("market_snapshot")


class MarketSnapshot:
    """市场快照生成器"""

    def __init__(self, trader: BitgetTrader, timeframes: List[str] = None):
        """
        初始化市场快照生成器

        Args:
            trader: 交易器实例
            timeframes: 时间周期列表，默认 ['5m', '15m', '1h', '4h']
        """
        self.trader = trader
        self.timeframes = timeframes or ['5m', '15m', '1h', '4h']

    async def fetch_snapshot(self) -> Dict:
        """
        异步获取市场快照

        Returns:
            包含所有时间周期数据的字典
        """
        snapshot = {
            'timestamp': datetime.now().isoformat(),
            'symbol': config.SYMBOL,
            'timeframes': {}
        }

        # 并发获取多时间周期数据
        tasks = []
        for tf in self.timeframes:
            tasks.append(self._fetch_timeframe_data(tf))

        results = await asyncio.gather(*tasks, return_exceptions=True)

        # 整合结果
        for tf, result in zip(self.timeframes, results):
            if isinstance(result, Exception):
                logger.error(f"获取{tf}数据失败: {result}")
                snapshot['timeframes'][tf] = {'error': str(result)}
            else:
                snapshot['timeframes'][tf] = result

        # 添加共识分析
        snapshot['consensus'] = self._analyze_consensus(snapshot)

        return snapshot

    async def _fetch_timeframe_data(self, timeframe: str) -> Dict:
        """
        获取单个时间周期的数据

        Args:
            timeframe: 时间周期（如 '15m', '1h'）

        Returns:
            包含价格、指标、市场状态、策略信号的字典
        """
        try:
            # 获取K线数据
            df = self.trader.fetch_ohlcv(
                symbol=config.SYMBOL,
                timeframe=timeframe,
                limit=config.KLINE_LIMIT
            )

            if df is None or df.empty:
                return {'error': 'No data available'}

            # 计算指标
            ind = IndicatorCalculator(df)

            # 价格信息
            current_price = df['close'].iloc[-1]
            price_change_24h = ((current_price - df['close'].iloc[-96]) / df['close'].iloc[-96] * 100) if len(df) >= 96 else 0

            price_info = {
                'current': float(current_price),
                'change_24h': float(price_change_24h)
            }

            # 技术指标
            indicators = self._calculate_indicators(ind)

            # 市场状态
            detector = MarketRegimeDetector(df)
            regime_info = detector.detect()

            market_regime = {
                'state': regime_info.regime.name if hasattr(regime_info.regime, 'name') else str(regime_info.regime),
                'confidence': float(regime_info.confidence),
                'details': {
                    'adx': float(regime_info.details.get('adx', 0)),
                    'bb_width_pct': float(regime_info.details.get('bb_width_pct', 0)),
                    'volatility': float(regime_info.details.get('volatility', 0))
                }
            }

            # 策略信号
            strategy_signals = self._analyze_strategies(df)

            return {
                'price': price_info,
                'indicators': indicators,
                'market_regime': market_regime,
                'strategy_signals': strategy_signals
            }

        except Exception as e:
            logger.error(f"获取{timeframe}数据失败: {e}")
            return {'error': str(e)}

    def _calculate_indicators(self, ind: IndicatorCalculator) -> Dict:
        """计算技术指标"""
        try:
            # RSI
            rsi = ind.rsi().iloc[-1]

            # MACD
            macd_data = ind.macd()
            macd = macd_data['macd'].iloc[-1]
            signal = macd_data['signal'].iloc[-1]
            histogram = macd_data['histogram'].iloc[-1]

            # EMA
            ema9 = ind.ema(9).iloc[-1]
            ema21 = ind.ema(21).iloc[-1]

            # ADX
            adx_data = ind.adx()
            adx = adx_data['adx'].iloc[-1]
            plus_di = adx_data['plus_di'].iloc[-1]
            minus_di = adx_data['minus_di'].iloc[-1]

            # Bollinger Bands
            bb = ind.bollinger_bands()
            bb_upper = bb['upper'].iloc[-1]
            bb_middle = bb['middle'].iloc[-1]
            bb_lower = bb['lower'].iloc[-1]
            # 计算布林带宽度百分比
            bb_width = ((bb_upper - bb_lower) / bb_middle * 100) if bb_middle != 0 else 0

            return {
                'rsi': float(rsi),
                'macd': {
                    'macd': float(macd),
                    'signal': float(signal),
                    'histogram': float(histogram)
                },
                'ema': {
                    'ema_9': float(ema9),
                    'ema_21': float(ema21),
                    'diff': float(ema9 - ema21)
                },
                'adx': {
                    'adx': float(adx),
                    'plus_di': float(plus_di),
                    'minus_di': float(minus_di)
                },
                'bollinger': {
                    'upper': float(bb_upper),
                    'middle': float(bb_middle),
                    'lower': float(bb_lower),
                    'width_pct': float(bb_width)
                }
            }
        except Exception as e:
            logger.error(f"计算指标失败: {e}")
            return {}

    def _analyze_strategies(self, df: pd.DataFrame) -> List[Dict]:
        """分析策略信号"""
        try:
            # 获取启用的策略
            if config.USE_DYNAMIC_STRATEGY:
                detector = MarketRegimeDetector(df)
                regime_info = detector.detect()
                strategies = detector.get_suitable_strategies(regime_info)
            else:
                strategies = config.ENABLE_STRATEGIES

            # 分析所有策略
            signals = analyze_all_strategies(df, strategies)

            # 转换为字典格式
            result = []
            for signal in signals:
                result.append({
                    'name': signal.strategy,
                    'signal': signal.signal.name,
                    'strength': float(signal.strength),
                    'confidence': float(signal.confidence),
                    'reason': signal.reason
                })

            return result
        except Exception as e:
            logger.error(f"分析策略失败: {e}")
            return []

    def _analyze_consensus(self, snapshot: Dict) -> Dict:
        """分析共识信号"""
        try:
            if not config.USE_CONSENSUS_SIGNAL:
                return {'enabled': False}

            # 收集所有时间周期的信号
            all_signals = []
            for tf_data in snapshot['timeframes'].values():
                if 'error' not in tf_data and 'strategy_signals' in tf_data:
                    all_signals.extend(tf_data['strategy_signals'])

            if not all_signals:
                return {
                    'enabled': True,
                    'result': 'no_signal',
                    'reason': 'No signals generated'
                }

            # 统计信号方向
            long_count = sum(1 for s in all_signals if s['signal'] == 'LONG')
            short_count = sum(1 for s in all_signals if s['signal'] == 'SHORT')
            total = len(all_signals)

            agreement = max(long_count, short_count) / total if total > 0 else 0

            return {
                'enabled': True,
                'long_count': long_count,
                'short_count': short_count,
                'total': total,
                'agreement': float(agreement),
                'result': 'consensus' if agreement >= config.MIN_STRATEGY_AGREEMENT else 'no_consensus',
                'reason': f"Agreement: {agreement:.1%} (threshold: {config.MIN_STRATEGY_AGREEMENT:.1%})"
            }
        except Exception as e:
            logger.error(f"分析共识失败: {e}")
            return {'enabled': True, 'error': str(e)}

    def to_json(self, snapshot: Dict) -> str:
        """输出JSON格式"""
        return json.dumps(snapshot, indent=2, ensure_ascii=False)

    def to_dashboard(self, snapshot: Dict) -> str:
        """输出Dashboard格式（ANSI彩色）"""
        from utils.market_formatter import MarketFormatter
        return MarketFormatter.format_dashboard(snapshot)
