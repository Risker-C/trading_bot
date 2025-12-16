"""
Claude工程护栏
确保Claude API调用的稳定性、成本控制和质量保证
"""
import json
import hashlib
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

import config
from logger_utils import get_logger

logger = get_logger("claude_guardrails")


class ClaudeGuardrails:
    """Claude工程护栏"""

    def __init__(self):
        # JSON Schema定义
        self.response_schema = {
            "type": "object",
            "required": ["execute", "confidence", "regime", "signal_quality"],
            "properties": {
                "execute": {"type": "boolean"},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                "regime": {"type": "string", "enum": ["trend", "mean_revert", "chop"]},
                "signal_quality": {"type": "number", "minimum": 0, "maximum": 1},
                "risk_flags": {"type": "array", "items": {"type": "string"}},
                "risk_level": {"type": "string"},
                "reason": {"type": "string"},
                "suggested_sl_pct": {"type": "number"},
                "suggested_tp_pct": {"type": "number"}
            }
        }

        # 缓存（去重）
        self.cache: Dict[str, Dict] = {}
        self.cache_ttl = getattr(config, 'CLAUDE_CACHE_TTL', 300)  # 5分钟

        # 预算控制
        self.daily_calls = 0
        self.daily_cost = 0.0
        self.last_reset_date = datetime.now().date()

        # 配置
        self.max_daily_calls = getattr(config, 'CLAUDE_MAX_DAILY_CALLS', 500)
        self.max_daily_cost = getattr(config, 'CLAUDE_MAX_DAILY_COST', 10.0)  # $10
        self.timeout = getattr(config, 'CLAUDE_TIMEOUT', 10)

        # 统计
        self.total_calls = 0
        self.cache_hits = 0
        self.validation_failures = 0
        self.timeout_failures = 0
        self.budget_stops = 0

    def _reset_daily_stats(self):
        """重置日统计"""
        today = datetime.now().date()
        if today > self.last_reset_date:
            logger.info(f"重置Claude日统计: 调用={self.daily_calls}, 成本=${self.daily_cost:.2f}")
            self.daily_calls = 0
            self.daily_cost = 0.0
            self.last_reset_date = today

    def _generate_cache_key(self, signal_data: Dict, indicators: Dict) -> str:
        """
        生成缓存键

        基于：
        - 策略名称
        - 信号类型
        - 当前K线时间戳（分钟级）
        - 关键指标（RSI、MACD、EMA等）
        """
        # 提取关键数据
        key_data = {
            'strategy': signal_data.get('strategy', ''),
            'signal': signal_data.get('signal', ''),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),  # 分钟级
            'rsi': round(indicators.get('rsi', 0), 1),
            'macd': round(indicators.get('macd', 0), 0),
            'ema_trend': 'up' if indicators.get('ema_short', 0) > indicators.get('ema_long', 0) else 'down',
            'adx': round(indicators.get('adx', 0), 0),
        }

        # 生成哈希
        key_str = json.dumps(key_data, sort_keys=True)
        return hashlib.md5(key_str.encode()).hexdigest()

    def check_cache(self, signal_data: Dict, indicators: Dict) -> Optional[Dict]:
        """
        检查缓存

        Args:
            signal_data: 信号数据
            indicators: 技术指标

        Returns:
            缓存的结果，如果没有则返回None
        """
        cache_key = self._generate_cache_key(signal_data, indicators)

        if cache_key in self.cache:
            cached = self.cache[cache_key]

            # 检查是否过期
            if datetime.now() - cached['timestamp'] < timedelta(seconds=self.cache_ttl):
                self.cache_hits += 1
                logger.debug(f"缓存命中: {cache_key[:8]}...")
                return cached['result']
            else:
                # 过期，删除
                del self.cache[cache_key]

        return None

    def save_cache(self, signal_data: Dict, indicators: Dict, result: Dict):
        """
        保存到缓存

        Args:
            signal_data: 信号数据
            indicators: 技术指标
            result: Claude分析结果
        """
        cache_key = self._generate_cache_key(signal_data, indicators)

        self.cache[cache_key] = {
            'timestamp': datetime.now(),
            'result': result
        }

        # 清理过期缓存
        self._cleanup_cache()

    def _cleanup_cache(self):
        """清理过期缓存"""
        now = datetime.now()
        expired_keys = [
            k for k, v in self.cache.items()
            if now - v['timestamp'] >= timedelta(seconds=self.cache_ttl)
        ]

        for key in expired_keys:
            del self.cache[key]

        if expired_keys:
            logger.debug(f"清理过期缓存: {len(expired_keys)}个")

    def validate_response(self, response_text: str) -> Tuple[bool, Optional[Dict], str]:
        """
        验证Claude响应

        Args:
            response_text: Claude响应文本

        Returns:
            (是否有效, 解析后的数据, 错误信息)
        """
        try:
            # 尝试解析JSON
            data = self._parse_json(response_text)

            if not data:
                self.validation_failures += 1
                return False, None, "无法解析JSON"

            # 验证必需字段
            required_fields = ['execute', 'confidence', 'regime', 'signal_quality']
            missing_fields = [f for f in required_fields if f not in data]

            if missing_fields:
                self.validation_failures += 1
                return False, None, f"缺少必需字段: {missing_fields}"

            # 验证数据类型和范围
            if not isinstance(data['execute'], bool):
                self.validation_failures += 1
                return False, None, "execute必须是布尔值"

            if not (0 <= data['confidence'] <= 1):
                self.validation_failures += 1
                return False, None, "confidence必须在0-1之间"

            if data['regime'] not in ['trend', 'mean_revert', 'chop']:
                self.validation_failures += 1
                return False, None, f"regime值无效: {data['regime']}"

            if not (0 <= data['signal_quality'] <= 1):
                self.validation_failures += 1
                return False, None, "signal_quality必须在0-1之间"

            # 验证通过
            return True, data, ""

        except Exception as e:
            self.validation_failures += 1
            return False, None, f"验证异常: {str(e)}"

    def _parse_json(self, text: str) -> Optional[Dict]:
        """
        解析JSON（支持多种格式）

        Args:
            text: 文本

        Returns:
            解析后的字典，失败返回None
        """
        # 尝试1: 直接解析
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试2: 提取JSON代码块
        import re
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(1))
            except json.JSONDecodeError:
                pass

        # 尝试3: 提取任何JSON对象
        json_match = re.search(r'\{.*\}', text, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group(0))
            except json.JSONDecodeError:
                pass

        return None

    def check_budget(self) -> Tuple[bool, str]:
        """
        检查预算

        Returns:
            (是否可以调用, 原因)
        """
        self._reset_daily_stats()

        # 检查调用次数
        if self.daily_calls >= self.max_daily_calls:
            self.budget_stops += 1
            return False, f"达到日调用上限({self.max_daily_calls})"

        # 检查成本
        if self.daily_cost >= self.max_daily_cost:
            self.budget_stops += 1
            return False, f"达到日成本上限(${self.max_daily_cost:.2f})"

        return True, "预算充足"

    def record_call(self, cost: float = 0.015):
        """
        记录一次调用

        Args:
            cost: 本次调用成本（默认$0.015，约为Sonnet的平均成本）
        """
        self.total_calls += 1
        self.daily_calls += 1
        self.daily_cost += cost

        logger.debug(f"记录Claude调用: 日调用={self.daily_calls}, 日成本=${self.daily_cost:.3f}")

    def get_fallback_decision(self, reason: str) -> Dict:
        """
        获取降级决策

        当Claude失败时，返回一个保守的默认决策

        Args:
            reason: 失败原因

        Returns:
            降级决策
        """
        failure_mode = getattr(config, 'CLAUDE_FAILURE_MODE', 'pass')

        if failure_mode == 'reject':
            # 保守模式：拒绝信号
            return {
                'execute': False,
                'confidence': 0.0,
                'regime': 'chop',
                'signal_quality': 0.0,
                'risk_flags': ['claude_failure'],
                'risk_level': '高',
                'reason': f"Claude失败，降级拒绝: {reason}",
            }
        else:
            # 通过模式：让信号通过，但标记低置信度
            return {
                'execute': True,
                'confidence': 0.5,
                'regime': 'chop',
                'signal_quality': 0.5,
                'risk_flags': ['claude_failure'],
                'risk_level': '中',
                'reason': f"Claude失败，降级通过: {reason}",
            }

    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            'total_calls': self.total_calls,
            'daily_calls': self.daily_calls,
            'daily_cost': self.daily_cost,
            'cache_hits': self.cache_hits,
            'cache_hit_rate': self.cache_hits / self.total_calls if self.total_calls > 0 else 0,
            'validation_failures': self.validation_failures,
            'timeout_failures': self.timeout_failures,
            'budget_stops': self.budget_stops,
            'cache_size': len(self.cache),
            'remaining_daily_calls': self.max_daily_calls - self.daily_calls,
            'remaining_daily_budget': self.max_daily_cost - self.daily_cost,
        }

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()

        print("\n" + "=" * 60)
        print("Claude护栏统计")
        print("=" * 60)
        print(f"总调用次数: {stats['total_calls']}")
        print(f"今日调用: {stats['daily_calls']} / {self.max_daily_calls}")
        print(f"今日成本: ${stats['daily_cost']:.2f} / ${self.max_daily_cost:.2f}")
        print(f"\n缓存命中: {stats['cache_hits']} ({stats['cache_hit_rate']:.1%})")
        print(f"缓存大小: {stats['cache_size']}")
        print(f"\n验证失败: {stats['validation_failures']}")
        print(f"超时失败: {stats['timeout_failures']}")
        print(f"预算停止: {stats['budget_stops']}")
        print(f"\n剩余调用: {stats['remaining_daily_calls']}")
        print(f"剩余预算: ${stats['remaining_daily_budget']:.2f}")
        print("=" * 60)


# 全局实例
_guardrails: Optional[ClaudeGuardrails] = None


def get_guardrails() -> ClaudeGuardrails:
    """获取Claude护栏单例"""
    global _guardrails
    if _guardrails is None:
        _guardrails = ClaudeGuardrails()
    return _guardrails
