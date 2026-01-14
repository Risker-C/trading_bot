"""
紧急熔断机制 (Emergency Circuit Breaker)
用于 Phase 1 优化的风险保护

功能：
1. 连续亏损熔断
2. 单日亏损熔断
3. 账户总资产熔断
4. 自动暂停交易
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict
import json
import os

logger = logging.getLogger(__name__)


class CircuitBreakerConfig:
    """熔断配置"""

    # 连续亏损熔断
    MAX_CONSECUTIVE_LOSSES = 3  # 连续亏损3次触发
    CONSECUTIVE_LOSS_PAUSE_MINUTES = 30  # 暂停30分钟

    # 单日亏损熔断
    MAX_DAILY_LOSS_PERCENT = 0.05  # 单日亏损5%触发
    DAILY_LOSS_PAUSE_MINUTES = 60  # 暂停60分钟

    # 账户总资产熔断
    MIN_ACCOUNT_BALANCE_PERCENT = 0.70  # 账户资产低于初始70%触发
    ACCOUNT_LOSS_PAUSE_MINUTES = 120  # 暂停120分钟

    # 状态文件路径
    STATE_FILE = "/root/trading_bot/circuit_breaker_state.json"


class EmergencyCircuitBreaker:
    """紧急熔断器"""

    def __init__(self, initial_balance: float):
        self.initial_balance = initial_balance
        self.consecutive_losses = 0
        self.daily_pnl = 0.0
        self.daily_start_balance = initial_balance
        self.is_paused = False
        self.pause_until: Optional[datetime] = None
        self.pause_reason = ""

        # 加载状态
        self._load_state()

        logger.info(f"[熔断器] 初始化完成，初始资金: {initial_balance:.2f} USDT")

    def _load_state(self):
        """加载熔断状态"""
        try:
            if os.path.exists(CircuitBreakerConfig.STATE_FILE):
                with open(CircuitBreakerConfig.STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.consecutive_losses = state.get('consecutive_losses', 0)
                    self.daily_pnl = state.get('daily_pnl', 0.0)
                    self.is_paused = state.get('is_paused', False)

                    pause_until_str = state.get('pause_until')
                    if pause_until_str:
                        self.pause_until = datetime.fromisoformat(pause_until_str)
                        # 检查是否已过暂停时间
                        if datetime.now() > self.pause_until:
                            self.is_paused = False
                            self.pause_until = None
                            logger.info("[熔断器] 暂停时间已过，恢复交易")

                    self.pause_reason = state.get('pause_reason', '')

                    logger.info(f"[熔断器] 加载状态: 连续亏损={self.consecutive_losses}, "
                              f"日内盈亏={self.daily_pnl:.2f}, 暂停={self.is_paused}")
        except Exception as e:
            logger.error(f"[熔断器] 加载状态失败: {e}")

    def _save_state(self):
        """保存熔断状态"""
        try:
            state = {
                'consecutive_losses': self.consecutive_losses,
                'daily_pnl': self.daily_pnl,
                'is_paused': self.is_paused,
                'pause_until': self.pause_until.isoformat() if self.pause_until else None,
                'pause_reason': self.pause_reason,
                'last_update': datetime.now().isoformat()
            }

            with open(CircuitBreakerConfig.STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"[熔断器] 保存状态失败: {e}")

    def check_trading_allowed(self) -> tuple[bool, str]:
        """
        检查是否允许交易

        Returns:
            (是否允许, 原因)
        """
        if self.is_paused:
            if self.pause_until and datetime.now() < self.pause_until:
                remaining = (self.pause_until - datetime.now()).total_seconds() / 60
                return False, f"熔断暂停中，剩余 {remaining:.1f} 分钟。原因: {self.pause_reason}"
            else:
                # 暂停时间已过，恢复交易
                self.is_paused = False
                self.pause_until = None
                self.pause_reason = ""
                self._save_state()
                logger.info("[熔断器] 暂停时间已过，恢复交易")
                return True, "交易已恢复"

        return True, "正常交易"

    def record_trade(self, pnl: float, current_balance: float):
        """
        记录交易结果并检查熔断条件

        Args:
            pnl: 交易盈亏
            current_balance: 当前账户余额
        """
        # 更新日内盈亏
        self.daily_pnl += pnl

        # 更新连续亏损计数
        if pnl < 0:
            self.consecutive_losses += 1
            logger.warning(f"[熔断器] 记录亏损: {pnl:.2f} USDT，连续亏损: {self.consecutive_losses}")
        else:
            self.consecutive_losses = 0
            logger.info(f"[熔断器] 记录盈利: {pnl:.2f} USDT，重置连续亏损计数")

        # 检查熔断条件
        self._check_circuit_breaker(current_balance)

        # 保存状态
        self._save_state()

    def _check_circuit_breaker(self, current_balance: float):
        """检查熔断条件"""
        # 1. 检查连续亏损
        if self.consecutive_losses >= CircuitBreakerConfig.MAX_CONSECUTIVE_LOSSES:
            self._trigger_pause(
                CircuitBreakerConfig.CONSECUTIVE_LOSS_PAUSE_MINUTES,
                f"连续亏损 {self.consecutive_losses} 次"
            )
            return

        # 2. 检查单日亏损
        daily_loss_pct = abs(self.daily_pnl / self.daily_start_balance)
        if self.daily_pnl < 0 and daily_loss_pct >= CircuitBreakerConfig.MAX_DAILY_LOSS_PERCENT:
            self._trigger_pause(
                CircuitBreakerConfig.DAILY_LOSS_PAUSE_MINUTES,
                f"单日亏损 {daily_loss_pct:.2%}（{self.daily_pnl:.2f} USDT）"
            )
            return

        # 3. 检查账户总资产
        balance_pct = current_balance / self.initial_balance
        if balance_pct <= CircuitBreakerConfig.MIN_ACCOUNT_BALANCE_PERCENT:
            self._trigger_pause(
                CircuitBreakerConfig.ACCOUNT_LOSS_PAUSE_MINUTES,
                f"账户资产跌至 {balance_pct:.2%}（{current_balance:.2f} USDT）"
            )
            return

    def _trigger_pause(self, pause_minutes: int, reason: str):
        """触发熔断暂停"""
        self.is_paused = True
        self.pause_until = datetime.now() + timedelta(minutes=pause_minutes)
        self.pause_reason = reason
        self._save_state()

        logger.error(f"[熔断器] 🚨 触发熔断！原因: {reason}")
        logger.error(f"[熔断器] 暂停交易 {pause_minutes} 分钟，恢复时间: {self.pause_until.strftime('%H:%M:%S')}")

    def reset_daily_stats(self):
        """重置日内统计（每日开始时调用）"""
        self.daily_pnl = 0.0
        self.daily_start_balance = self.initial_balance
        self.consecutive_losses = 0
        self._save_state()
        logger.info("[熔断器] 重置日内统计")

    def get_status(self) -> Dict:
        """获取熔断器状态"""
        return {
            'is_paused': self.is_paused,
            'pause_reason': self.pause_reason,
            'pause_until': self.pause_until.isoformat() if self.pause_until else None,
            'consecutive_losses': self.consecutive_losses,
            'daily_pnl': self.daily_pnl,
            'daily_loss_pct': (self.daily_pnl / self.daily_start_balance) if self.daily_start_balance > 0 else 0
        }
