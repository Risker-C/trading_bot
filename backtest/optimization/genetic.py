"""
遗传算法 - 小规模参数优化（种群20，迭代50）
"""
import random
import numpy as np
from typing import Dict, List, Any, Callable, Optional, Tuple
import asyncio


class GeneticOptimizer:
    """遗传算法优化器"""

    def __init__(
        self,
        backtest_func: Callable,
        population_size: int = 20,
        generations: int = 50,
        mutation_rate: float = 0.1,
        crossover_rate: float = 0.7
    ):
        """
        Args:
            backtest_func: 回测函数
            population_size: 种群大小
            generations: 迭代次数
            mutation_rate: 变异率
            crossover_rate: 交叉率
        """
        self.backtest_func = backtest_func
        self.population_size = population_size
        self.generations = generations
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate

    async def optimize(
        self,
        search_space: Dict[str, Dict[str, Any]],
        target_metric: str = 'sharpe',
        progress_callback: Optional[Callable] = None
    ) -> List[Dict[str, Any]]:
        """
        执行遗传算法优化

        Args:
            search_space: 参数空间定义，如 {'period': {'type': 'int', 'min': 5, 'max': 50}}
            target_metric: 目标指标
            progress_callback: 进度回调

        Returns:
            优化结果列表
        """
        # 初始化种群
        population = self._initialize_population(search_space)

        best_individual = None
        best_score = float('-inf')
        results = []

        for gen in range(self.generations):
            # 评估种群
            fitness_scores = []
            for individual in population:
                try:
                    metrics = await self.backtest_func(individual)
                    score = metrics.get(target_metric, 0)
                    fitness_scores.append(score)

                    # 记录结果（扁平化结构）
                    results.append({
                        'params': individual.copy(),
                        'metrics': metrics,
                        'score': score,
                        'generation': gen,
                        'run_id': metrics.get('run_id'),
                        'param_set_id': metrics.get('param_set_id')
                    })

                    # 更新最佳个体
                    if score > best_score:
                        best_score = score
                        best_individual = individual.copy()

                except Exception as e:
                    fitness_scores.append(float('-inf'))

            # 进度回调
            if progress_callback:
                await progress_callback({
                    'generation': gen + 1,
                    'total_generations': self.generations,
                    'progress': (gen + 1) / self.generations,
                    'best_score': best_score,
                    'best_params': best_individual
                })

            # 选择
            selected = self._selection(population, fitness_scores)

            # 交叉和变异
            next_population = []
            for i in range(0, len(selected), 2):
                parent1 = selected[i]
                parent2 = selected[i + 1] if i + 1 < len(selected) else selected[0]

                if random.random() < self.crossover_rate:
                    child1, child2 = self._crossover(parent1, parent2, search_space)
                else:
                    child1, child2 = parent1.copy(), parent2.copy()

                if random.random() < self.mutation_rate:
                    child1 = self._mutate(child1, search_space)
                if random.random() < self.mutation_rate:
                    child2 = self._mutate(child2, search_space)

                next_population.extend([child1, child2])

            population = next_population[:self.population_size]

            await asyncio.sleep(0)

        # 返回Top 50结果
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:50]

    def _initialize_population(self, search_space: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """初始化种群"""
        population = []
        for _ in range(self.population_size):
            individual = {}
            for param_name, param_def in search_space.items():
                if param_def['type'] == 'int':
                    individual[param_name] = random.randint(param_def['min'], param_def['max'])
                elif param_def['type'] == 'float':
                    individual[param_name] = random.uniform(param_def['min'], param_def['max'])
            population.append(individual)
        return population

    def _selection(self, population: List[Dict], fitness_scores: List[float]) -> List[Dict]:
        """锦标赛选择（k=3）"""
        selected = []
        for _ in range(self.population_size):
            # 随机选3个个体
            indices = random.sample(range(len(population)), min(3, len(population)))
            best_idx = max(indices, key=lambda i: fitness_scores[i])
            selected.append(population[best_idx].copy())
        return selected

    def _crossover(
        self,
        parent1: Dict[str, Any],
        parent2: Dict[str, Any],
        search_space: Dict[str, Dict[str, Any]]
    ) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        """单点交叉"""
        child1, child2 = parent1.copy(), parent2.copy()
        params = list(search_space.keys())

        if len(params) > 1:
            crossover_point = random.randint(1, len(params) - 1)
            for i in range(crossover_point, len(params)):
                param = params[i]
                child1[param], child2[param] = child2[param], child1[param]

        return child1, child2

    def _mutate(self, individual: Dict[str, Any], search_space: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
        """高斯变异"""
        mutated = individual.copy()
        param = random.choice(list(search_space.keys()))
        param_def = search_space[param]

        if param_def['type'] == 'int':
            delta = int(np.random.normal(0, (param_def['max'] - param_def['min']) * 0.1))
            mutated[param] = np.clip(
                individual[param] + delta,
                param_def['min'],
                param_def['max']
            )
        elif param_def['type'] == 'float':
            delta = np.random.normal(0, (param_def['max'] - param_def['min']) * 0.1)
            mutated[param] = np.clip(
                individual[param] + delta,
                param_def['min'],
                param_def['max']
            )

        return mutated
