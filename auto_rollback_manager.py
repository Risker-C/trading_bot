"""
自动回滚管理器 (Auto Rollback Manager)
用于 Phase 1 优化的配置回滚保护

功能：
1. 监控系统性能指标
2. 自动检测性能下降
3. 自动回滚到备份配置
4. 记录回滚历史
"""

import logging
import shutil
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import json

logger = logging.getLogger(__name__)


class RollbackConfig:
    """回滚配置"""

    # 性能监控阈值
    MAX_DAILY_LOSS_FOR_ROLLBACK = 0.05  # 单日亏损5%触发回滚
    MIN_WIN_RATE_FOR_ROLLBACK = 0.30    # 胜率低于30%触发回滚
    MAX_DRAWDOWN_FOR_ROLLBACK = 0.15    # 最大回撤15%触发回滚

    # 监控周期
    MONITORING_PERIOD_HOURS = 24  # 监控24小时数据
    MIN_TRADES_FOR_EVALUATION = 10  # 最少10笔交易才评估

    # 文件路径
    BACKUP_DIR = "/root/trading_bot/config_backups"
    ROLLBACK_STATE_FILE = "/root/trading_bot/rollback_state.json"
    CURRENT_CONFIG = "/root/trading_bot/config.py"


class AutoRollbackManager:
    """自动回滚管理器"""

    def __init__(self):
        self.rollback_history: List[Dict] = []
        self.last_check_time: Optional[datetime] = None
        self.performance_data: Dict = {}

        # 加载状态
        self._load_state()

        logger.info("[回滚管理器] 初始化完成")

    def _load_state(self):
        """加载回滚状态"""
        try:
            if os.path.exists(RollbackConfig.ROLLBACK_STATE_FILE):
                with open(RollbackConfig.ROLLBACK_STATE_FILE, 'r') as f:
                    state = json.load(f)
                    self.rollback_history = state.get('rollback_history', [])

                    last_check_str = state.get('last_check_time')
                    if last_check_str:
                        self.last_check_time = datetime.fromisoformat(last_check_str)

                    self.performance_data = state.get('performance_data', {})

                    logger.info(f"[回滚管理器] 加载状态: {len(self.rollback_history)} 次历史回滚")
        except Exception as e:
            logger.error(f"[回滚管理器] 加载状态失败: {e}")

    def _save_state(self):
        """保存回滚状态"""
        try:
            state = {
                'rollback_history': self.rollback_history,
                'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
                'performance_data': self.performance_data,
                'last_update': datetime.now().isoformat()
            }

            with open(RollbackConfig.ROLLBACK_STATE_FILE, 'w') as f:
                json.dump(state, f, indent=2)
        except Exception as e:
            logger.error(f"[回滚管理器] 保存状态失败: {e}")

    def check_performance_and_rollback(self, trades_data: List[Dict]) -> bool:
        """
        检查性能并决定是否回滚

        Args:
            trades_data: 交易数据列表，每个元素包含 {pnl, timestamp, ...}

        Returns:
            是否触发了回滚
        """
        if len(trades_data) < RollbackConfig.MIN_TRADES_FOR_EVALUATION:
            logger.info(f"[回滚管理器] 交易数量不足 ({len(trades_data)}/{RollbackConfig.MIN_TRADES_FOR_EVALUATION})，跳过评估")
            return False

        # 计算性能指标
        metrics = self._calculate_metrics(trades_data)

        # 检查是否需要回滚
        should_rollback, reason = self._should_rollback(metrics)

        if should_rollback:
            logger.error(f"[回滚管理器] 🔄 触发回滚！原因: {reason}")
            self._execute_rollback(reason, metrics)
            return True

        logger.info(f"[回滚管理器] 性能正常，无需回滚。胜率: {metrics['win_rate']:.2%}, 日亏损: {metrics['daily_loss_pct']:.2%}")
        return False

    def _calculate_metrics(self, trades_data: List[Dict]) -> Dict:
        """计算性能指标"""
        total_pnl = sum(t['pnl'] for t in trades_data)
        wins = [t for t in trades_data if t['pnl'] > 0]
        losses = [t for t in trades_data if t['pnl'] < 0]

        win_rate = len(wins) / len(trades_data) if trades_data else 0

        # 计算最大回撤
        cumulative_pnl = 0
        peak = 0
        max_drawdown = 0
        for trade in trades_data:
            cumulative_pnl += trade['pnl']
            peak = max(peak, cumulative_pnl)
            drawdown = (peak - cumulative_pnl) / abs(peak) if peak != 0 else 0
            max_drawdown = max(max_drawdown, drawdown)

        return {
            'total_pnl': total_pnl,
            'win_rate': win_rate,
            'max_drawdown': max_drawdown,
            'daily_loss_pct': abs(total_pnl / 1000) if total_pnl < 0 else 0,  # 假设初始1000 USDT
            'trade_count': len(trades_data)
        }

    def _should_rollback(self, metrics: Dict) -> tuple[bool, str]:
        """判断是否应该回滚"""
        # 1. 检查单日亏损
        if metrics['daily_loss_pct'] >= RollbackConfig.MAX_DAILY_LOSS_FOR_ROLLBACK:
            return True, f"单日亏损 {metrics['daily_loss_pct']:.2%} 超过阈值"

        # 2. 检查胜率
        if metrics['win_rate'] < RollbackConfig.MIN_WIN_RATE_FOR_ROLLBACK:
            return True, f"胜率 {metrics['win_rate']:.2%} 低于阈值"

        # 3. 检查最大回撤
        if metrics['max_drawdown'] >= RollbackConfig.MAX_DRAWDOWN_FOR_ROLLBACK:
            return True, f"最大回撤 {metrics['max_drawdown']:.2%} 超过阈值"

        return False, ""

    def _execute_rollback(self, reason: str, metrics: Dict):
        """执行配置回滚"""
        try:
            # 查找最新的备份文件
            backup_files = sorted(
                [f for f in os.listdir(RollbackConfig.BACKUP_DIR) if f.startswith('config_backup_')],
                reverse=True
            )

            if not backup_files:
                logger.error("[回滚管理器] 未找到备份文件，无法回滚")
                return

            latest_backup = os.path.join(RollbackConfig.BACKUP_DIR, backup_files[0])

            # 备份当前配置（以防回滚失败）
            emergency_backup = f"{RollbackConfig.CURRENT_CONFIG}.emergency_backup"
            shutil.copy2(RollbackConfig.CURRENT_CONFIG, emergency_backup)

            # 执行回滚
            shutil.copy2(latest_backup, RollbackConfig.CURRENT_CONFIG)

            # 记录回滚历史
            rollback_record = {
                'timestamp': datetime.now().isoformat(),
                'reason': reason,
                'metrics': metrics,
                'backup_file': latest_backup
            }
            self.rollback_history.append(rollback_record)
            self._save_state()

            logger.error(f"[回滚管理器] ✅ 配置已回滚到: {backup_files[0]}")
            logger.error(f"[回滚管理器] 回滚原因: {reason}")

        except Exception as e:
            logger.error(f"[回滚管理器] 回滚失败: {e}")

    def get_rollback_history(self) -> List[Dict]:
        """获取回滚历史"""
        return self.rollback_history

    def get_status(self) -> Dict:
        """获取回滚管理器状态"""
        return {
            'rollback_count': len(self.rollback_history),
            'last_rollback': self.rollback_history[-1] if self.rollback_history else None,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None
        }
