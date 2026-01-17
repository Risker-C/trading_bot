"""
配置管理服务 - 支持将回测参数应用到生产环境
"""
import json
from typing import Dict, Any, List
from datetime import datetime


class ConfigService:
    """配置管理服务"""

    def __init__(self, config_path: str = "config/strategy_config.json"):
        self.config_path = config_path

    async def apply_config(
        self,
        strategy_name: str,
        params: Dict[str, Any],
        dry_run: bool = True
    ) -> Dict[str, Any]:
        """
        应用配置到生产环境

        Args:
            strategy_name: 策略名称
            params: 参数配置
            dry_run: 是否为预演模式（不实际修改）

        Returns:
            应用结果（包含diff和警告）
        """
        # 读取当前配置
        try:
            with open(self.config_path, 'r') as f:
                current_config = json.load(f)
        except FileNotFoundError:
            current_config = {}

        # 获取当前策略配置
        current_params = current_config.get(strategy_name, {})

        # 计算差异
        diff = self._calculate_diff(current_params, params)

        # 生成警告
        warnings = self._generate_warnings(diff)

        if not dry_run:
            # 实际应用配置
            current_config[strategy_name] = params

            # 保存配置
            with open(self.config_path, 'w') as f:
                json.dump(current_config, f, indent=2)

            # 记录变更历史
            await self._log_change(strategy_name, current_params, params)

        return {
            'success': True,
            'dry_run': dry_run,
            'strategy': strategy_name,
            'diff': diff,
            'warnings': warnings,
            'applied_at': int(datetime.utcnow().timestamp()) if not dry_run else None
        }

    def _calculate_diff(
        self,
        old_params: Dict[str, Any],
        new_params: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """计算参数差异"""
        diff = []

        # 检查修改和新增
        for key, new_value in new_params.items():
            if key not in old_params:
                diff.append({
                    'type': 'added',
                    'key': key,
                    'old_value': None,
                    'new_value': new_value
                })
            elif old_params[key] != new_value:
                diff.append({
                    'type': 'modified',
                    'key': key,
                    'old_value': old_params[key],
                    'new_value': new_value
                })

        # 检查删除
        for key in old_params:
            if key not in new_params:
                diff.append({
                    'type': 'removed',
                    'key': key,
                    'old_value': old_params[key],
                    'new_value': None
                })

        return diff

    def _generate_warnings(self, diff: List[Dict[str, Any]]) -> List[str]:
        """生成警告信息"""
        warnings = []

        for change in diff:
            if change['type'] == 'removed':
                warnings.append(f"⚠️ 参数 '{change['key']}' 将被删除")

            elif change['type'] == 'modified':
                # 检查是否为关键参数的大幅变化
                if isinstance(change['old_value'], (int, float)) and isinstance(change['new_value'], (int, float)):
                    change_pct = abs(change['new_value'] - change['old_value']) / abs(change['old_value']) if change['old_value'] != 0 else 1
                    if change_pct > 0.5:
                        warnings.append(
                            f"⚠️ 参数 '{change['key']}' 变化超过50%: "
                            f"{change['old_value']} → {change['new_value']}"
                        )

        if not warnings:
            warnings.append("✅ 无重大风险")

        return warnings

    async def _log_change(
        self,
        strategy_name: str,
        old_params: Dict[str, Any],
        new_params: Dict[str, Any]
    ):
        """记录配置变更历史"""
        # TODO: 实现变更历史记录（可以存储到数据库或文件）
        pass

    async def get_config_history(self, strategy_name: str) -> List[Dict[str, Any]]:
        """获取配置变更历史"""
        # TODO: 从数据库或文件读取历史记录
        return []
