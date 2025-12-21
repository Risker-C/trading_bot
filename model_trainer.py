#!/usr/bin/env python3
"""
ML模型训练脚本

从历史交易数据中训练信号质量预测模型
"""

import sys
import os
import sqlite3
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import joblib

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from logger_utils import get_logger
from feature_engineer import FeatureEngineer

logger = get_logger("model_trainer")


class ModelTrainer:
    """ML模型训练器"""

    def __init__(self, db_path: str = "trading_bot.db"):
        """
        初始化训练器

        Args:
            db_path: 数据库路径
        """
        self.db_path = db_path
        self.feature_engineer = FeatureEngineer()
        self.model = None
        self.scaler = None

    def load_historical_data(self, days: int = 180) -> pd.DataFrame:
        """
        从数据库加载历史交易数据

        Args:
            days: 加载最近N天的数据

        Returns:
            交易数据DataFrame
        """
        logger.info(f"从数据库加载最近{days}天的交易数据...")

        conn = sqlite3.connect(self.db_path)

        # 查询历史交易记录（包含开仓和平仓）
        query = f"""
            SELECT
                id, order_id, symbol, side, action,
                amount, price, value_usdt, pnl, pnl_percent,
                strategy, reason, status, created_at,
                filled_price, filled_time, fee
            FROM trades
            WHERE datetime(created_at) > datetime('now', '-{days} days')
            ORDER BY created_at
        """

        df = pd.read_sql_query(query, conn)
        conn.close()

        logger.info(f"✓ 加载了 {len(df)} 条交易记录")

        return df

    def prepare_training_data(self, trades_df: pd.DataFrame) -> pd.DataFrame:
        """
        准备训练数据

        Args:
            trades_df: 交易记录DataFrame

        Returns:
            训练数据DataFrame（包含特征和标签）
        """
        logger.info("准备训练数据...")

        # 注意：这是一个简化版本
        # 实际使用时需要：
        # 1. 从交易所API获取历史K线数据
        # 2. 计算技术指标
        # 3. 匹配开仓和平仓记录
        # 4. 提取特征

        logger.warning("⚠️ 当前版本使用模拟数据进行演示")
        logger.warning("⚠️ 实际使用时需要实现完整的数据准备流程")

        # TODO: 实现完整的数据准备流程
        # 1. 获取历史K线数据
        # 2. 计算技术指标
        # 3. 提取特征
        # 4. 生成标签

        return pd.DataFrame()

    def generate_labels(self, trades_df: pd.DataFrame) -> pd.Series:
        """
        生成训练标签

        Args:
            trades_df: 交易记录DataFrame

        Returns:
            标签Series（1=盈利，0=亏损）
        """
        logger.info("生成训练标签...")

        # 匹配开仓和平仓记录
        open_trades = trades_df[trades_df['action'] == 'open'].copy()
        close_trades = trades_df[trades_df['action'] == 'close'].copy()

        labels = []

        for _, open_trade in open_trades.iterrows():
            # 查找对应的平仓记录
            # 简化版本：假设按顺序匹配
            # 实际需要更复杂的匹配逻辑

            # 根据盈亏生成标签
            # 这里需要实现完整的匹配逻辑
            pass

        return pd.Series(labels)

    def train_model(self, X: pd.DataFrame, y: pd.Series):
        """
        训练模型

        Args:
            X: 特征DataFrame
            y: 标签Series
        """
        logger.info("开始训练模型...")

        try:
            import lightgbm as lgb
            from sklearn.model_selection import train_test_split
            from sklearn.preprocessing import StandardScaler
            from sklearn.metrics import accuracy_score, precision_score, recall_score, roc_auc_score

            # 分割训练集和测试集
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )

            logger.info(f"训练集: {len(X_train)} 样本")
            logger.info(f"测试集: {len(X_test)} 样本")

            # 标准化特征
            self.scaler = StandardScaler()
            X_train_scaled = self.scaler.fit_transform(X_train)
            X_test_scaled = self.scaler.transform(X_test)

            # 训练LightGBM模型
            logger.info("训练LightGBM模型...")

            self.model = lgb.LGBMClassifier(
                n_estimators=100,
                learning_rate=0.05,
                max_depth=5,
                num_leaves=31,
                min_child_samples=20,
                subsample=0.8,
                colsample_bytree=0.8,
                random_state=42,
                verbose=-1
            )

            self.model.fit(
                X_train_scaled, y_train,
                eval_set=[(X_test_scaled, y_test)],
                eval_metric='auc',
                callbacks=[lgb.early_stopping(stopping_rounds=10, verbose=False)]
            )

            # 评估模型
            y_pred = self.model.predict(X_test_scaled)
            y_pred_proba = self.model.predict_proba(X_test_scaled)[:, 1]

            accuracy = accuracy_score(y_test, y_pred)
            precision = precision_score(y_test, y_pred)
            recall = recall_score(y_test, y_pred)
            auc = roc_auc_score(y_test, y_pred_proba)

            logger.info("=" * 60)
            logger.info("模型评估结果")
            logger.info("=" * 60)
            logger.info(f"准确率 (Accuracy):  {accuracy:.4f}")
            logger.info(f"精确率 (Precision): {precision:.4f}")
            logger.info(f"召回率 (Recall):    {recall:.4f}")
            logger.info(f"AUC-ROC:           {auc:.4f}")
            logger.info("=" * 60)

            # 特征重要性
            feature_importance = pd.DataFrame({
                'feature': X.columns,
                'importance': self.model.feature_importances_
            }).sort_values('importance', ascending=False)

            logger.info("\n前10个重要特征:")
            for idx, row in feature_importance.head(10).iterrows():
                logger.info(f"  {row['feature']}: {row['importance']:.4f}")

            return {
                'accuracy': accuracy,
                'precision': precision,
                'recall': recall,
                'auc': auc,
                'feature_importance': feature_importance
            }

        except ImportError as e:
            logger.error(f"✗ 缺少依赖包: {e}")
            logger.error("请安装: pip install lightgbm scikit-learn")
            return None

    def save_model(self, output_path: str = None):
        """
        保存模型

        Args:
            output_path: 输出路径
        """
        if self.model is None:
            logger.error("✗ 没有训练好的模型可以保存")
            return

        output_path = output_path or config.ML_MODEL_PATH

        # 创建目录
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)

        # 保存模型
        model_data = {
            'model': self.model,
            'scaler': self.scaler,
            'feature_names': self.feature_engineer.get_feature_names(),
            'trained_at': datetime.now().isoformat(),
            'config': {
                'lookback': config.ML_FEATURE_LOOKBACK,
                'threshold': config.ML_QUALITY_THRESHOLD
            }
        }

        joblib.dump(model_data, output_path)
        logger.info(f"✓ 模型已保存到: {output_path}")

    def train_demo_model(self):
        """
        训练演示模型（使用模拟数据）

        用于测试和演示，实际使用时需要真实数据
        """
        logger.info("=" * 60)
        logger.info("训练演示模型（使用模拟数据）")
        logger.info("=" * 60)

        try:
            import lightgbm as lgb
            from sklearn.preprocessing import StandardScaler

            # 生成模拟数据
            logger.info("生成模拟训练数据...")

            np.random.seed(42)
            n_samples = 1000

            # 模拟特征
            feature_names = self.feature_engineer.get_feature_names()
            n_features = len(feature_names)

            X = pd.DataFrame(
                np.random.randn(n_samples, n_features),
                columns=feature_names
            )

            # 模拟标签（基于一些特征的简单规则）
            # 信号质量高 = 信号强度高 + 策略一致性高 + RSI适中
            y = (
                (X['signal_strength'] > 0) &
                (X['strategy_agreement'] > 0) &
                (X['rsi'] > -0.5) &
                (X['rsi'] < 0.5)
            ).astype(int)

            # 添加一些噪音
            noise_idx = np.random.choice(n_samples, size=int(n_samples * 0.2), replace=False)
            y.iloc[noise_idx] = 1 - y.iloc[noise_idx]

            logger.info(f"生成了 {n_samples} 个样本")
            logger.info(f"正样本: {y.sum()} ({y.mean():.1%})")
            logger.info(f"负样本: {(1-y).sum()} ({(1-y).mean():.1%})")

            # 训练模型
            metrics = self.train_model(X, y)

            if metrics:
                # 保存模型
                self.save_model()
                logger.info("✓ 演示模型训练完成")
                return True
            else:
                logger.error("✗ 演示模型训练失败")
                return False

        except Exception as e:
            logger.error(f"✗ 训练演示模型失败: {e}")
            import traceback
            traceback.print_exc()
            return False


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("ML模型训练脚本")
    print("=" * 60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    trainer = ModelTrainer()

    # 检查是否有足够的历史数据
    trades_df = trainer.load_historical_data(days=180)

    if len(trades_df) < config.ML_MIN_TRAINING_SAMPLES:
        logger.warning(f"⚠️ 历史数据不足（{len(trades_df)} < {config.ML_MIN_TRAINING_SAMPLES}）")
        logger.info("将训练演示模型用于测试...")

        # 训练演示模型
        success = trainer.train_demo_model()

        if success:
            logger.info("\n" + "=" * 60)
            logger.info("✓ 演示模型训练成功")
            logger.info("=" * 60)
            logger.info("\n重要提示:")
            logger.info("1. 当前模型使用模拟数据训练，仅用于测试")
            logger.info("2. 实际使用时需要收集足够的历史数据（至少100笔交易）")
            logger.info("3. 建议先在影子模式下运行，收集数据后重新训练")
            logger.info("4. 训练真实模型的步骤:")
            logger.info("   - 运行机器人至少1-2周，收集交易数据")
            logger.info("   - 实现完整的数据准备流程（获取K线、计算指标）")
            logger.info("   - 重新运行此脚本训练真实模型")
            logger.info("=" * 60)
        else:
            logger.error("\n✗ 演示模型训练失败")
            sys.exit(1)

    else:
        logger.info(f"✓ 找到 {len(trades_df)} 条历史交易记录")
        logger.warning("⚠️ 完整的训练流程尚未实现")
        logger.info("请参考文档实现完整的数据准备和训练流程")

    print(f"\n结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)


if __name__ == "__main__":
    main()
