#!/usr/bin/env python3
"""
日志分流功能测试脚本

测试内容：
1. 验证日志分流配置是否生效
2. 验证各级别日志是否正确写入对应文件
3. 验证 ERROR 日志不会写入 info.log
4. 验证控制台聚合观察视图
5. 验证日志文件轮转配置
6. 验证 LevelFilter 过滤器功能
7. 验证向后兼容模式
"""

import sys
import os
from datetime import datetime
import time
import glob

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config
from utils.logger_utils import get_logger, LevelFilter
import logging


class TestLogSplitting:
    """日志分流测试类"""

    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.total = 0
        self.test_logger = None
        self.log_dir = getattr(config, 'LOG_DIR', 'logs')

    def run_test(self, test_name: str, test_func):
        """运行单个测试"""
        self.total += 1
        print(f"\n{'='*60}")
        print(f"测试 {self.total}: {test_name}")
        print(f"{'='*60}")

        try:
            test_func()
            self.passed += 1
            print(f"✅ 测试通过: {test_name}")
            return True
        except AssertionError as e:
            self.failed += 1
            print(f"❌ 测试失败: {test_name}")
            print(f"   错误: {e}")
            return False
        except Exception as e:
            self.failed += 1
            print(f"❌ 测试异常: {test_name}")
            print(f"   异常: {e}")
            import traceback
            traceback.print_exc()
            return False

    def print_summary(self):
        """打印测试摘要"""
        print(f"\n{'='*60}")
        print("测试摘要")
        print(f"{'='*60}")
        print(f"总计: {self.total}")
        print(f"通过: {self.passed} ✅")
        print(f"失败: {self.failed} ❌")
        print(f"成功率: {(self.passed/self.total*100):.1f}%")
        print(f"{'='*60}\n")

        return self.failed == 0

    def cleanup_test_logs(self):
        """清理测试日志文件"""
        print("\n清理测试日志文件...")
        log_files = [
            'debug.log', 'info.log', 'warning.log', 'error.log',
            'debug.log.*', 'info.log.*', 'warning.log.*', 'error.log.*'
        ]
        for pattern in log_files:
            for file in glob.glob(os.path.join(self.log_dir, pattern)):
                try:
                    os.remove(file)
                    print(f"  删除: {file}")
                except Exception as e:
                    print(f"  删除失败: {file}, 错误: {e}")


def test_config_validation():
    """测试1: 配置验证"""
    print("\n检查日志分流配置...")

    # 检查必要的配置项
    assert hasattr(config, 'ENABLE_LOG_SPLITTING'), "缺少 ENABLE_LOG_SPLITTING 配置"
    assert hasattr(config, 'LOG_FILE_INFO'), "缺少 LOG_FILE_INFO 配置"
    assert hasattr(config, 'LOG_FILE_ERROR'), "缺少 LOG_FILE_ERROR 配置"
    assert hasattr(config, 'LOG_FILE_DEBUG'), "缺少 LOG_FILE_DEBUG 配置"
    assert hasattr(config, 'LOG_FILE_WARNING'), "缺少 LOG_FILE_WARNING 配置"

    print(f"  ENABLE_LOG_SPLITTING: {config.ENABLE_LOG_SPLITTING}")
    print(f"  LOG_FILE_INFO: {config.LOG_FILE_INFO}")
    print(f"  LOG_FILE_ERROR: {config.LOG_FILE_ERROR}")
    print(f"  LOG_FILE_DEBUG: {config.LOG_FILE_DEBUG}")
    print(f"  LOG_FILE_WARNING: {config.LOG_FILE_WARNING}")

    # 检查轮转配置
    assert hasattr(config, 'LOG_ROTATION_WHEN'), "缺少 LOG_ROTATION_WHEN 配置"
    assert hasattr(config, 'LOG_ROTATION_INTERVAL'), "缺少 LOG_ROTATION_INTERVAL 配置"
    assert hasattr(config, 'LOG_ROTATION_BACKUP_COUNT'), "缺少 LOG_ROTATION_BACKUP_COUNT 配置"

    print(f"  LOG_ROTATION_WHEN: {config.LOG_ROTATION_WHEN}")
    print(f"  LOG_ROTATION_INTERVAL: {config.LOG_ROTATION_INTERVAL}")
    print(f"  LOG_ROTATION_BACKUP_COUNT: {config.LOG_ROTATION_BACKUP_COUNT}")

    # 检查控制台配置
    assert hasattr(config, 'CONSOLE_LOG_LEVEL'), "缺少 CONSOLE_LOG_LEVEL 配置"
    assert hasattr(config, 'CONSOLE_SHOW_ALL_LEVELS'), "缺少 CONSOLE_SHOW_ALL_LEVELS 配置"

    print(f"  CONSOLE_LOG_LEVEL: {config.CONSOLE_LOG_LEVEL}")
    print(f"  CONSOLE_SHOW_ALL_LEVELS: {config.CONSOLE_SHOW_ALL_LEVELS}")

    print("\n✓ 所有配置项验证通过")


def test_logger_creation():
    """测试2: Logger 创建"""
    print("\n创建测试 logger...")

    logger = get_logger("test_log_splitting")
    assert logger is not None, "Logger 创建失败"
    assert isinstance(logger, logging.Logger), "Logger 类型错误"

    print(f"  Logger 名称: {logger.name}")
    print(f"  Logger 级别: {logging.getLevelName(logger.level)}")
    print(f"  Handler 数量: {len(logger.handlers)}")

    # 检查 handler 数量
    if config.ENABLE_LOG_SPLITTING:
        # 分流模式：4 个文件 handler + 1 个控制台 handler = 5
        expected_handlers = 5
    else:
        # 单文件模式：1 个文件 handler + 1 个控制台 handler = 2
        expected_handlers = 2

    assert len(logger.handlers) == expected_handlers, \
        f"Handler 数量错误，期望 {expected_handlers}，实际 {len(logger.handlers)}"

    # 打印 handler 信息
    for i, handler in enumerate(logger.handlers):
        print(f"  Handler {i+1}: {type(handler).__name__}")
        if hasattr(handler, 'baseFilename'):
            print(f"    文件: {handler.baseFilename}")
        print(f"    级别: {logging.getLevelName(handler.level)}")

    print("\n✓ Logger 创建成功")


def test_level_filter():
    """测试3: LevelFilter 过滤器"""
    print("\n测试 LevelFilter 过滤器...")

    # 测试精确匹配模式
    info_filter = LevelFilter(logging.INFO, exact=True)

    # 创建测试记录
    debug_record = logging.LogRecord(
        name="test", level=logging.DEBUG, pathname="", lineno=0,
        msg="debug", args=(), exc_info=None
    )
    info_record = logging.LogRecord(
        name="test", level=logging.INFO, pathname="", lineno=0,
        msg="info", args=(), exc_info=None
    )
    error_record = logging.LogRecord(
        name="test", level=logging.ERROR, pathname="", lineno=0,
        msg="error", args=(), exc_info=None
    )

    # 测试过滤
    assert not info_filter.filter(debug_record), "DEBUG 应该被过滤"
    assert info_filter.filter(info_record), "INFO 应该通过"
    assert not info_filter.filter(error_record), "ERROR 应该被过滤"

    print("  ✓ 精确匹配模式测试通过")

    # 测试范围匹配模式
    error_filter = LevelFilter(logging.ERROR, exact=False)

    assert not error_filter.filter(debug_record), "DEBUG 应该被过滤"
    assert not error_filter.filter(info_record), "INFO 应该被过滤"
    assert error_filter.filter(error_record), "ERROR 应该通过"

    # 测试 CRITICAL
    critical_record = logging.LogRecord(
        name="test", level=logging.CRITICAL, pathname="", lineno=0,
        msg="critical", args=(), exc_info=None
    )
    assert error_filter.filter(critical_record), "CRITICAL 应该通过"

    print("  ✓ 范围匹配模式测试通过")
    print("\n✓ LevelFilter 过滤器测试通过")


def test_log_file_creation():
    """测试4: 日志文件创建"""
    print("\n测试日志文件创建...")

    # 创建 logger 并写入测试日志
    logger = get_logger("test_file_creation")

    # 写入各级别日志
    logger.debug("测试 DEBUG 日志")
    logger.info("测试 INFO 日志")
    logger.warning("测试 WARNING 日志")
    logger.error("测试 ERROR 日志")

    # 等待日志写入
    time.sleep(0.5)

    # 检查日志文件是否创建
    log_dir = getattr(config, 'LOG_DIR', 'logs')

    if config.ENABLE_LOG_SPLITTING:
        # 检查分流模式的日志文件
        expected_files = [
            config.LOG_FILE_DEBUG,
            config.LOG_FILE_INFO,
            config.LOG_FILE_WARNING,
            config.LOG_FILE_ERROR
        ]

        for log_file in expected_files:
            file_path = os.path.join(log_dir, log_file)
            assert os.path.exists(file_path), f"日志文件不存在: {file_path}"
            print(f"  ✓ 文件存在: {log_file}")

            # 检查文件大小
            file_size = os.path.getsize(file_path)
            assert file_size > 0, f"日志文件为空: {log_file}"
            print(f"    大小: {file_size} 字节")

    else:
        # 检查单文件模式
        log_file = config.LOG_FILE
        file_path = os.path.join(log_dir, log_file)
        assert os.path.exists(file_path), f"日志文件不存在: {file_path}"
        print(f"  ✓ 文件存在: {log_file}")

    print("\n✓ 日志文件创建成功")


def test_log_content_separation():
    """测试5: 日志内容分离"""
    print("\n测试日志内容分离...")

    if not config.ENABLE_LOG_SPLITTING:
        print("  跳过测试（日志分流未启用）")
        return

    # 创建 logger 并写入测试日志
    logger = get_logger("test_separation")

    test_messages = {
        'DEBUG': "这是一条 DEBUG 测试消息",
        'INFO': "这是一条 INFO 测试消息",
        'WARNING': "这是一条 WARNING 测试消息",
        'ERROR': "这是一条 ERROR 测试消息"
    }

    logger.debug(test_messages['DEBUG'])
    logger.info(test_messages['INFO'])
    logger.warning(test_messages['WARNING'])
    logger.error(test_messages['ERROR'])

    # 等待日志写入
    time.sleep(0.5)

    log_dir = getattr(config, 'LOG_DIR', 'logs')

    # 检查 debug.log
    debug_file = os.path.join(log_dir, config.LOG_FILE_DEBUG)
    with open(debug_file, 'r', encoding='utf-8') as f:
        debug_content = f.read()
    assert test_messages['DEBUG'] in debug_content, "DEBUG 消息未写入 debug.log"
    assert test_messages['INFO'] not in debug_content, "INFO 消息错误写入 debug.log"
    assert test_messages['ERROR'] not in debug_content, "ERROR 消息错误写入 debug.log"
    print("  ✓ debug.log 内容正确")

    # 检查 info.log
    info_file = os.path.join(log_dir, config.LOG_FILE_INFO)
    with open(info_file, 'r', encoding='utf-8') as f:
        info_content = f.read()
    assert test_messages['INFO'] in info_content, "INFO 消息未写入 info.log"
    assert test_messages['DEBUG'] not in info_content, "DEBUG 消息错误写入 info.log"
    assert test_messages['ERROR'] not in info_content, "ERROR 消息错误写入 info.log"
    print("  ✓ info.log 内容正确（ERROR 未写入）")

    # 检查 warning.log
    warning_file = os.path.join(log_dir, config.LOG_FILE_WARNING)
    with open(warning_file, 'r', encoding='utf-8') as f:
        warning_content = f.read()
    assert test_messages['WARNING'] in warning_content, "WARNING 消息未写入 warning.log"
    assert test_messages['INFO'] not in warning_content, "INFO 消息错误写入 warning.log"
    assert test_messages['ERROR'] not in warning_content, "ERROR 消息错误写入 warning.log"
    print("  ✓ warning.log 内容正确")

    # 检查 error.log
    error_file = os.path.join(log_dir, config.LOG_FILE_ERROR)
    with open(error_file, 'r', encoding='utf-8') as f:
        error_content = f.read()
    assert test_messages['ERROR'] in error_content, "ERROR 消息未写入 error.log"
    assert test_messages['INFO'] not in error_content, "INFO 消息错误写入 error.log"
    assert test_messages['DEBUG'] not in error_content, "DEBUG 消息错误写入 error.log"
    print("  ✓ error.log 内容正确")

    print("\n✓ 日志内容分离正确")


def test_log_format():
    """测试6: 日志格式"""
    print("\n测试日志格式...")

    logger = get_logger("test_format")
    test_message = "格式测试消息_12345"

    logger.info(test_message)
    time.sleep(0.5)

    log_dir = getattr(config, 'LOG_DIR', 'logs')

    if config.ENABLE_LOG_SPLITTING:
        log_file = os.path.join(log_dir, config.LOG_FILE_INFO)
    else:
        log_file = os.path.join(log_dir, config.LOG_FILE)

    with open(log_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # 找到测试消息所在行
    test_line = None
    for line in lines:
        if test_message in line:
            test_line = line
            break

    assert test_line is not None, "未找到测试消息"

    # 验证日志格式：YYYY-MM-DD HH:MM:SS [LEVEL] [name] message
    import re
    pattern = r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2} \[INFO\] \[test_format\] 格式测试消息_12345'
    assert re.search(pattern, test_line), f"日志格式不正确: {test_line}"

    print(f"  日志行: {test_line.strip()}")
    print("  ✓ 日志格式正确")

    print("\n✓ 日志格式测试通过")


def test_handler_count():
    """测试7: Handler 数量验证"""
    print("\n测试 Handler 数量...")

    logger = get_logger("test_handler_count")

    if config.ENABLE_LOG_SPLITTING:
        # 分流模式：4 个文件 handler + 1 个控制台 handler
        expected = 5
        print(f"  分流模式，期望 {expected} 个 handler")
    else:
        # 单文件模式：1 个文件 handler + 1 个控制台 handler
        expected = 2
        print(f"  单文件模式，期望 {expected} 个 handler")

    actual = len(logger.handlers)
    print(f"  实际 handler 数量: {actual}")

    assert actual == expected, f"Handler 数量不匹配，期望 {expected}，实际 {actual}"

    # 验证 handler 类型
    from logging.handlers import TimedRotatingFileHandler, RotatingFileHandler
    import logging

    file_handlers = 0
    console_handlers = 0

    for handler in logger.handlers:
        if isinstance(handler, (TimedRotatingFileHandler, RotatingFileHandler)):
            file_handlers += 1
            print(f"  ✓ 文件 handler: {type(handler).__name__}")
        elif isinstance(handler, logging.StreamHandler):
            console_handlers += 1
            print(f"  ✓ 控制台 handler: {type(handler).__name__}")

    assert console_handlers == 1, f"控制台 handler 数量错误: {console_handlers}"

    if config.ENABLE_LOG_SPLITTING:
        assert file_handlers == 4, f"文件 handler 数量错误: {file_handlers}"
    else:
        assert file_handlers == 1, f"文件 handler 数量错误: {file_handlers}"

    print("\n✓ Handler 数量验证通过")


def test_performance():
    """测试8: 性能测试"""
    print("\n测试日志性能...")

    logger = get_logger("test_performance")

    # 测试写入 1000 条日志的时间
    start_time = time.time()
    for i in range(1000):
        logger.info(f"性能测试消息 {i}")
    end_time = time.time()

    elapsed = end_time - start_time
    avg_time = elapsed / 1000 * 1000  # 转换为毫秒

    print(f"  写入 1000 条日志耗时: {elapsed:.3f} 秒")
    print(f"  平均每条日志: {avg_time:.3f} 毫秒")

    # 性能要求：平均每条日志不超过 10 毫秒
    assert avg_time < 10, f"日志性能不达标: {avg_time:.3f} ms/条"

    print("\n✓ 日志性能测试通过")


def main():
    """主测试函数"""
    print("\n" + "="*60)
    print("日志分流功能测试")
    print("="*60)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*60)

    tester = TestLogSplitting()

    # 清理旧的测试日志
    tester.cleanup_test_logs()

    # 运行所有测试
    tester.run_test("配置验证", test_config_validation)
    tester.run_test("Logger 创建", test_logger_creation)
    tester.run_test("LevelFilter 过滤器", test_level_filter)
    tester.run_test("日志文件创建", test_log_file_creation)
    tester.run_test("日志内容分离", test_log_content_separation)
    tester.run_test("日志格式", test_log_format)
    tester.run_test("Handler 数量验证", test_handler_count)
    tester.run_test("性能测试", test_performance)

    # 打印摘要
    success = tester.print_summary()

    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # 显示日志文件信息
    print("\n" + "="*60)
    print("日志文件信息")
    print("="*60)
    log_dir = getattr(config, 'LOG_DIR', 'logs')
    for file in os.listdir(log_dir):
        if file.endswith('.log') or '.log.' in file:
            file_path = os.path.join(log_dir, file)
            size = os.path.getsize(file_path)
            print(f"  {file}: {size} 字节")

    # 返回退出码
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
