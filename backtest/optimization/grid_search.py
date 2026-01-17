"""
网格搜索算法 - 串行执行参数组合
"""
import itertools
from typing import Dict, List, Any, Callable, Optional
import asyncio


class GridSearchOptimizer:
    """网格搜索优化器"""

    def __init__(self, backtest_func: Callable):
        """
        Args:
            backtest_func: 回测函数，接收参数字典，返回指标字典
        """
        self.backtest_func = backtest_func

    async def optimize(
        self,
        search_space: Dict[str, List[Any]],
        target_metric: str = 'sharpe',
        max_results: int = 50,
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        执行网格搜索

        Args:
            search_space: 参数搜索空间，如 {'period': [10, 20, 30], 'threshold': [0.5, 1.0]}
            target_metric: 目标优化指标
            max_results: 保留Top N结果
            progress_callback: 进度回调函数

        Returns:
            优化结果列表（按score降序）
        """
        # 生成所有参数组合
        param_names = list(search_space.keys())
        param_values = list(search_space.values())
        combinations = list(itertools.product(*param_values))

        total = len(combinations)
        results = []

        # 串行执行每个组合
        for idx, combo in enumerate(combinations):
            params = dict(zip(param_names, combo))

            try:
                # 执行回测
                metrics = await self.backtest_func(params)

                # 扁平化结构，将 run_id 和 param_set_id 提升到顶层
                result = {
                    'params': params,
                    'metrics': metrics,
                    'score': metrics.get(target_metric, 0),
                    'run_id': metrics.get('run_id'),
                    'param_set_id': metrics.get('param_set_id')
                }
                results.append(result)

                # 进度回调
                if progress_callback:
                    await progress_callback({
                        'completed': idx + 1,
                        'total': total,
                        'progress': (idx + 1) / total,
                        'current_params': params,
                        'current_score': result['score']
                    })

            except Exception as e:
                # 记录失败但继续
                print(f"参数组合失败: {params}, 错误: {e}")

            # 避免阻塞事件循环
            await asyncio.sleep(0)

        # 按score排序并保留Top N
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:max_results]

    def get_search_space_size(self, search_space: Dict[str, List[Any]]) -> int:
        """计算搜索空间大小"""
        size = 1
        for values in search_space.values():
            size *= len(values)
        return size
