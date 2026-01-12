"""
API 错误码定义和异常类
"""
from enum import Enum
from typing import Any, Dict, Optional


class ErrorCode(str, Enum):
    """API 错误码枚举"""

    # 认证相关错误 (401)
    INVALID_CREDENTIALS = "INVALID_CREDENTIALS"
    INVALID_TOKEN = "INVALID_TOKEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"

    # 权限相关错误 (403)
    FORBIDDEN = "FORBIDDEN"

    # 资源相关错误 (404)
    NOT_FOUND = "NOT_FOUND"
    TRADE_NOT_FOUND = "TRADE_NOT_FOUND"
    POSITION_NOT_FOUND = "POSITION_NOT_FOUND"

    # 验证相关错误 (422)
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INVALID_PARAMETER = "INVALID_PARAMETER"

    # 限流相关错误 (429)
    RATE_LIMIT = "RATE_LIMIT"

    # 服务器相关错误 (500)
    INTERNAL_ERROR = "INTERNAL_ERROR"
    DATABASE_ERROR = "DATABASE_ERROR"
    SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE"


class APIException(Exception):
    """API 自定义异常类"""

    def __init__(
        self,
        error_code: ErrorCode,
        message: Optional[str] = None,
        http_status: int = 500,
        details: Optional[Dict[str, Any]] = None
    ):
        """
        初始化 API 异常

        Args:
            error_code: 错误码
            message: 错误消息（可选，默认使用错误码对应的消息）
            http_status: HTTP 状态码
            details: 错误详情（可选）
        """
        self.error_code = error_code
        self.message = message or self._get_default_message(error_code)
        self.http_status = http_status
        self.details = details or {}
        super().__init__(self.message)

    @staticmethod
    def _get_default_message(error_code: ErrorCode) -> str:
        """获取错误码对应的默认消息"""
        messages = {
            ErrorCode.INVALID_CREDENTIALS: "Invalid username or password",
            ErrorCode.INVALID_TOKEN: "Invalid authentication token",
            ErrorCode.TOKEN_EXPIRED: "Authentication token has expired",
            ErrorCode.FORBIDDEN: "Access forbidden",
            ErrorCode.NOT_FOUND: "Resource not found",
            ErrorCode.TRADE_NOT_FOUND: "Trade not found",
            ErrorCode.POSITION_NOT_FOUND: "Position not found",
            ErrorCode.VALIDATION_ERROR: "Validation error",
            ErrorCode.INVALID_PARAMETER: "Invalid parameter",
            ErrorCode.RATE_LIMIT: "Rate limit exceeded",
            ErrorCode.INTERNAL_ERROR: "Internal server error",
            ErrorCode.DATABASE_ERROR: "Database error",
            ErrorCode.SERVICE_UNAVAILABLE: "Service temporarily unavailable",
        }
        return messages.get(error_code, "Unknown error")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": {
                "code": self.error_code.value,
                "message": self.message,
                "details": self.details
            }
        }


# 预定义的异常实例，方便使用
class AuthenticationError(APIException):
    """认证错误"""
    def __init__(self, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code=ErrorCode.INVALID_CREDENTIALS,
            message=message,
            http_status=401,
            details=details
        )


class TokenError(APIException):
    """Token 错误"""
    def __init__(self, message: Optional[str] = None, expired: bool = False, details: Optional[Dict[str, Any]] = None):
        error_code = ErrorCode.TOKEN_EXPIRED if expired else ErrorCode.INVALID_TOKEN
        super().__init__(
            error_code=error_code,
            message=message,
            http_status=401,
            details=details
        )


class NotFoundError(APIException):
    """资源不存在错误"""
    def __init__(self, resource: str = "Resource", message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code=ErrorCode.NOT_FOUND,
            message=message or f"{resource} not found",
            http_status=404,
            details=details
        )


class ValidationError(APIException):
    """验证错误"""
    def __init__(self, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code=ErrorCode.VALIDATION_ERROR,
            message=message,
            http_status=422,
            details=details
        )


class RateLimitError(APIException):
    """限流错误"""
    def __init__(self, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code=ErrorCode.RATE_LIMIT,
            message=message,
            http_status=429,
            details=details
        )


class DatabaseError(APIException):
    """数据库错误"""
    def __init__(self, message: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        super().__init__(
            error_code=ErrorCode.DATABASE_ERROR,
            message=message,
            http_status=500,
            details=details
        )
