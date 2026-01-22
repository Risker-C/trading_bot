"""
批量写入缓冲器 - 优化 Supabase 写入性能
"""
import time
from typing import List, Dict, Any
from backtest.adapters.storage.supabase_client import get_supabase_client
from utils.logger_utils import get_logger


class BatchWriter:
    """
    批量写入缓冲器

    减少 HTTP 往返次数,提升写入性能

    示例:
        with BatchWriter('backtest_klines', batch_size=1000) as writer:
            for kline in klines:
                writer.add({'session_id': sid, 'ts': kline['ts'], ...})
        # 自动 flush
    """

    def __init__(self, table_name: str, batch_size: int = 500):
        """
        Args:
            table_name: 表名
            batch_size: 批量大小 (默认 500)
        """
        self.client = get_supabase_client()
        self.logger = get_logger("supabase.batch_writer")
        self.table_name = table_name
        self.batch_size = batch_size
        self.buffer: List[Dict[str, Any]] = []
        self.logger.debug(
            "BatchWriter init table=%s batch_size=%s",
            self.table_name,
            self.batch_size
        )

    def add(self, record: Dict[str, Any]):
        """
        添加记录到缓冲

        Args:
            record: 记录字典
        """
        self.buffer.append(record)
        if len(self.buffer) >= self.batch_size:
            self.flush()

    def flush(self):
        """提交缓冲的所有记录"""
        if not self.buffer:
            return

        try:
            start = time.monotonic()
            self.client.table(self.table_name).insert(self.buffer).execute()
            elapsed = time.monotonic() - start
            self.logger.debug(
                "BatchWriter flush ok table=%s rows=%s elapsed=%.3fs",
                self.table_name,
                len(self.buffer),
                elapsed
            )
            self.buffer.clear()
        except Exception as e:
            self.logger.exception(
                "BatchWriter flush failed table=%s rows=%s",
                self.table_name,
                len(self.buffer)
            )
            # 如果批量插入失败,尝试逐行插入以找出问题
            failed_records = []
            for i, record in enumerate(self.buffer):
                try:
                    self.client.table(self.table_name).insert(record).execute()
                except Exception as row_err:
                    self.logger.error(
                        "BatchWriter row failed table=%s index=%s error=%s",
                        self.table_name,
                        i,
                        row_err
                    )
                    failed_records.append((i, record, str(row_err)))

            self.buffer.clear()

            if failed_records:
                error_details = "\n".join([
                    f"  Record {i}: {err}" for i, _, err in failed_records
                ])
                raise Exception(
                    f"BatchWriter failed to insert {len(failed_records)} records:\n{error_details}"
                ) from e

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.flush()
