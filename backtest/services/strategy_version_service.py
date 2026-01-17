"""
策略版本管理服务
"""
import hashlib
import json
import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime


class StrategyVersionService:
    """策略版本管理服务"""

    def __init__(self, repo):
        self.repo = repo

    async def create_strategy_version(
        self,
        name: str,
        version: str,
        params_schema: Dict[str, Any],
        code: Optional[str] = None
    ) -> str:
        """
        创建策略版本

        Args:
            name: 策略名称
            version: 版本号
            params_schema: 参数Schema定义
            code: 策略代码（可选，用于计算hash）

        Returns:
            策略版本ID
        """
        version_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())

        # 计算代码hash
        if code:
            code_hash = hashlib.sha256(code.encode()).hexdigest()
        else:
            code_hash = hashlib.sha256(json.dumps(params_schema).encode()).hexdigest()

        conn = self.repo._get_conn()

        # 检查是否已存在
        cursor = conn.execute("""
            SELECT id FROM strategy_versions
            WHERE name = ? AND version = ?
        """, (name, version))

        existing = cursor.fetchone()
        if existing:
            conn.close()
            return existing[0]

        # 创建新版本
        conn.execute("""
            INSERT INTO strategy_versions
            (id, name, version, params_schema, code_hash, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            version_id,
            name,
            version,
            json.dumps(params_schema),
            code_hash,
            now
        ))
        conn.commit()
        conn.close()

        return version_id

    async def get_strategy_version(self, version_id: str) -> Optional[Dict[str, Any]]:
        """获取策略版本信息"""
        conn = self.repo._get_conn()
        cursor = conn.execute("""
            SELECT id, name, version, params_schema, code_hash, created_at
            FROM strategy_versions WHERE id = ?
        """, (version_id,))

        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return {
            'id': row[0],
            'name': row[1],
            'version': row[2],
            'params_schema': json.loads(row[3]),
            'code_hash': row[4],
            'created_at': row[5]
        }

    async def list_strategy_versions(self, name: Optional[str] = None) -> List[Dict[str, Any]]:
        """列出策略版本"""
        conn = self.repo._get_conn()

        if name:
            cursor = conn.execute("""
                SELECT id, name, version, params_schema, code_hash, created_at
                FROM strategy_versions WHERE name = ?
                ORDER BY created_at DESC
            """, (name,))
        else:
            cursor = conn.execute("""
                SELECT id, name, version, params_schema, code_hash, created_at
                FROM strategy_versions
                ORDER BY created_at DESC
            """)

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'id': row[0],
                'name': row[1],
                'version': row[2],
                'params_schema': json.loads(row[3]),
                'code_hash': row[4],
                'created_at': row[5]
            }
            for row in rows
        ]

    async def create_parameter_set(
        self,
        strategy_version_id: str,
        params: Dict[str, Any],
        source: str = 'manual'
    ) -> str:
        """创建参数集"""
        param_set_id = str(uuid.uuid4())
        now = int(datetime.utcnow().timestamp())

        conn = self.repo._get_conn()
        conn.execute("""
            INSERT INTO parameter_sets
            (id, strategy_version_id, params, source, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            param_set_id,
            strategy_version_id,
            json.dumps(params),
            source,
            now
        ))
        conn.commit()
        conn.close()

        return param_set_id
