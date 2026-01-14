"""
Ticker 数据模型
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Ticker(BaseModel):
    """实时行情数据模型"""

    symbol: str = Field(..., description="交易对符号")
    last: Optional[float] = Field(None, description="最新成交价")
    bid: Optional[float] = Field(None, description="买一价")
    ask: Optional[float] = Field(None, description="卖一价")
    volume: Optional[float] = Field(None, description="24小时成交量")
    change_24h: Optional[float] = Field(None, description="24小时涨跌幅(%)")
    high_24h: Optional[float] = Field(None, description="24小时最高价")
    low_24h: Optional[float] = Field(None, description="24小时最低价")
    timestamp: datetime = Field(default_factory=datetime.now, description="数据时间戳")
    stale: bool = Field(False, description="数据是否过期")

    class Config:
        json_schema_extra = {
            "example": {
                "symbol": "BTCUSDT",
                "last": 95142.50,
                "bid": 95140.00,
                "ask": 95145.00,
                "volume": 12345.67,
                "change_24h": 1.52,
                "high_24h": 96000.00,
                "low_24h": 93500.00,
                "timestamp": "2026-01-14T18:30:00",
                "stale": False
            }
        }
