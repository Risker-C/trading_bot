#!/usr/bin/env python3
"""
Gemini API 性能测试脚本
测试 Gemini API 调用并监控系统资源占用
"""

import os
import sys
import time
import psutil
import threading
from datetime import datetime
from typing import Dict, List, Optional
import json
import requests

# 尝试导入 Google Gemini SDK
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("⚠️ google-generativeai 未安装，请运行: pip install google-generativeai")

# 检查是否使用代理
USE_PROXY = bool(os.getenv('GOOGLE_GEMINI_BASE_URL'))

# 资源监控类
class ResourceMonitor:
    """系统资源监控器"""

    def __init__(self, interval: float = 0.1):
        """
        初始化资源监控器

        Args:
            interval: 采样间隔（秒）
        """
        self.interval = interval
        self.monitoring = False
        self.monitor_thread = None
        self.samples = []
        self.process = psutil.Process()

    def start(self):
        """开始监控"""
        self.monitoring = True
        self.samples = []
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()
        print(f"✅ 资源监控已启动 (采样间隔: {self.interval}s)")

    def stop(self):
        """停止监控"""
        self.monitoring = False
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        print(f"✅ 资源监控已停止 (共采集 {len(self.samples)} 个样本)")

    def _monitor_loop(self):
        """监控循环"""
        while self.monitoring:
            try:
                # 采集当前资源使用情况
                sample = {
                    'timestamp': time.time(),
                    'cpu_percent': self.process.cpu_percent(interval=None),
                    'memory_mb': self.process.memory_info().rss / 1024 / 1024,
                    'memory_percent': self.process.memory_percent(),
                    'threads': self.process.num_threads(),
                }

                # 系统级资源
                sample['system_cpu'] = psutil.cpu_percent(interval=None)
                sample['system_memory'] = psutil.virtual_memory().percent

                self.samples.append(sample)
                time.sleep(self.interval)

            except Exception as e:
                print(f"⚠️ 监控采样失败: {e}")

    def get_stats(self) -> Dict:
        """获取统计信息"""
        if not self.samples:
            return {}

        cpu_values = [s['cpu_percent'] for s in self.samples]
        memory_values = [s['memory_mb'] for s in self.samples]
        system_cpu_values = [s['system_cpu'] for s in self.samples]
        system_memory_values = [s['system_memory'] for s in self.samples]

        return {
            'samples_count': len(self.samples),
            'duration_seconds': self.samples[-1]['timestamp'] - self.samples[0]['timestamp'],
            'process': {
                'cpu_percent': {
                    'min': min(cpu_values),
                    'max': max(cpu_values),
                    'avg': sum(cpu_values) / len(cpu_values),
                },
                'memory_mb': {
                    'min': min(memory_values),
                    'max': max(memory_values),
                    'avg': sum(memory_values) / len(memory_values),
                },
                'threads': self.samples[-1]['threads'],
            },
            'system': {
                'cpu_percent': {
                    'min': min(system_cpu_values),
                    'max': max(system_cpu_values),
                    'avg': sum(system_cpu_values) / len(system_cpu_values),
                },
                'memory_percent': {
                    'min': min(system_memory_values),
                    'max': max(system_memory_values),
                    'avg': sum(system_memory_values) / len(system_memory_values),
                },
            }
        }

    def print_stats(self):
        """打印统计信息"""
        stats = self.get_stats()
        if not stats:
            print("⚠️ 没有采集到数据")
            return

        print("\n" + "="*80)
        print("📊 资源使用统计")
        print("="*80)

        print(f"\n⏱️  监控时长: {stats['duration_seconds']:.2f} 秒")
        print(f"📈 采样数量: {stats['samples_count']} 个")

        print("\n🔹 进程资源使用:")
        print(f"  CPU: 最小={stats['process']['cpu_percent']['min']:.1f}% | "
              f"平均={stats['process']['cpu_percent']['avg']:.1f}% | "
              f"最大={stats['process']['cpu_percent']['max']:.1f}%")
        print(f"  内存: 最小={stats['process']['memory_mb']['min']:.1f}MB | "
              f"平均={stats['process']['memory_mb']['avg']:.1f}MB | "
              f"最大={stats['process']['memory_mb']['max']:.1f}MB")
        print(f"  线程数: {stats['process']['threads']}")

        print("\n🔹 系统资源使用:")
        print(f"  CPU: 最小={stats['system']['cpu_percent']['min']:.1f}% | "
              f"平均={stats['system']['cpu_percent']['avg']:.1f}% | "
              f"最大={stats['system']['cpu_percent']['max']:.1f}%")
        print(f"  内存: 最小={stats['system']['memory_percent']['min']:.1f}% | "
              f"平均={stats['system']['memory_percent']['avg']:.1f}% | "
              f"最大={stats['system']['memory_percent']['max']:.1f}%")

        # 检查是否有资源占用过高的情况
        if stats['process']['cpu_percent']['max'] > 80:
            print("\n⚠️  警告: 进程CPU占用峰值超过80%")
        if stats['system']['cpu_percent']['max'] > 90:
            print("\n⚠️  警告: 系统CPU占用峰值超过90%")
        if stats['process']['memory_mb']['max'] > 1000:
            print("\n⚠️  警告: 进程内存占用峰值超过1GB")


# 代理客户端类
class ProxyGeminiClient:
    """使用 HTTP 请求调用代理服务的 Gemini 客户端"""

    def __init__(self, api_key: str, base_url: str, debug: bool = False):
        """
        初始化代理客户端

        Args:
            api_key: API Key
            base_url: 代理服务的 base URL
            debug: 是否启用调试模式
        """
        self.api_key = api_key
        self.base_url = base_url.rstrip('/')
        self.debug = debug
        self.session = requests.Session()

        # 添加浏览器请求头以绕过 Cloudflare 基本检查
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
            'Sec-Fetch-Dest': 'empty',
            'Sec-Fetch-Mode': 'cors',
            'Sec-Fetch-Site': 'same-origin',
        })

        # 尝试多种认证方式
        self.auth_methods = [
            {'Authorization': f'Bearer {api_key}'},
            {'x-api-key': api_key},
            {'api-key': api_key},
            {'X-API-Key': api_key},
        ]

    def generate_content(self, prompt: str, max_tokens: int = 1000) -> Dict:
        """
        生成内容

        Args:
            prompt: 提示词
            max_tokens: 最大 token 数

        Returns:
            响应对象（模拟 SDK 的响应格式）
        """
        # 尝试不同的 API 端点格式
        endpoints = [
            f"{self.base_url}/v1/chat/completions",
            f"{self.base_url}/chat/completions",
            f"{self.base_url}/v1/messages",
            f"{self.base_url}/api/chat",
            f"{self.base_url}",  # 直接使用 base_url
        ]

        payload = {
            "model": "gemini-pro",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens
        }

        last_error = None
        attempts = []

        # 尝试不同的端点和认证方式组合
        for endpoint in endpoints:
            for auth_headers in self.auth_methods:
                try:
                    headers = {
                        'Content-Type': 'application/json',
                        **auth_headers
                    }

                    if self.debug:
                        print(f"\n🔍 尝试: {endpoint}")
                        print(f"   认证: {list(auth_headers.keys())[0]}")

                    response = self.session.post(endpoint, json=payload, headers=headers, timeout=30)

                    if self.debug:
                        print(f"   状态码: {response.status_code}")

                    response.raise_for_status()
                    data = response.json()

                    # 解析响应（适配不同的响应格式）
                    text = self._extract_text(data)

                    if self.debug:
                        print(f"   ✅ 成功!")

                    # 返回模拟的响应对象
                    class Response:
                        def __init__(self, text):
                            self.text = text

                    return Response(text)

                except Exception as e:
                    last_error = e
                    attempts.append(f"{endpoint} ({list(auth_headers.keys())[0]}): {str(e)[:50]}")
                    continue

        # 尝试将 API key 作为 URL 参数
        if self.debug:
            print("\n🔍 尝试使用 URL 参数传递 API key...")

        for endpoint in endpoints[:3]:  # 只尝试前3个端点
            try:
                url_with_key = f"{endpoint}?key={self.api_key}"
                if self.debug:
                    print(f"\n🔍 尝试: {endpoint}?key=...")

                response = self.session.post(
                    url_with_key,
                    json=payload,
                    headers={'Content-Type': 'application/json'},
                    timeout=30
                )

                if self.debug:
                    print(f"   状态码: {response.status_code}")

                response.raise_for_status()
                data = response.json()
                text = self._extract_text(data)

                if self.debug:
                    print(f"   ✅ 成功!")

                class Response:
                    def __init__(self, text):
                        self.text = text

                return Response(text)

            except Exception as e:
                last_error = e
                continue

        # 所有端点都失败
        if self.debug:
            print("\n❌ 所有尝试都失败:")
            for attempt in attempts[:5]:  # 只显示前5个
                print(f"   - {attempt}")

        raise Exception(f"所有 API 端点调用失败: {last_error}")

    def _extract_text(self, data: Dict) -> str:
        """从响应中提取文本"""
        # OpenAI 格式
        if 'choices' in data:
            return data['choices'][0]['message']['content']
        # Anthropic 格式
        elif 'content' in data:
            if isinstance(data['content'], list):
                return data['content'][0]['text']
            return data['content']
        # 直接文本
        elif 'text' in data:
            return data['text']
        else:
            return str(data)


# Gemini 测试类
class GeminiTester:
    """Gemini API 测试器"""

    def __init__(self, api_key: Optional[str] = None):
        """
        初始化 Gemini 测试器

        Args:
            api_key: Gemini API Key
        """
        self.api_key = api_key or os.getenv('GEMINI_API_KEY') or os.getenv('GOOGLE_API_KEY')
        self.base_url = os.getenv('GOOGLE_GEMINI_BASE_URL')
        self.model = None
        self.use_proxy = bool(self.base_url)
        self.enabled = bool(self.api_key)

        if not self.api_key:
            print("❌ 未配置 GEMINI_API_KEY 或 GOOGLE_API_KEY")
            return

        try:
            if self.use_proxy:
                # 使用代理模式（启用调试）
                self.model = ProxyGeminiClient(self.api_key, self.base_url, debug=True)
                print(f"✅ Gemini 代理客户端初始化成功")
                print(f"   Base URL: {self.base_url}")
                print(f"   调试模式: 已启用")
            else:
                # 使用官方 SDK
                if not GEMINI_AVAILABLE:
                    print("❌ Gemini SDK 未安装")
                    self.enabled = False
                    return

                genai.configure(api_key=self.api_key)
                self.model = genai.GenerativeModel('gemini-pro')
                print(f"✅ Gemini 官方客户端初始化成功 (模型: gemini-pro)")
        except Exception as e:
            self.enabled = False
            print(f"❌ Gemini 客户端初始化失败: {e}")

    def test_simple_call(self, monitor: ResourceMonitor) -> Dict:
        """
        测试简单的 API 调用

        Args:
            monitor: 资源监控器

        Returns:
            测试结果
        """
        if not self.enabled:
            return {'success': False, 'error': 'Gemini 未启用'}

        print("\n" + "="*80)
        print("测试 1: 简单的 API 调用")
        print("="*80)

        try:
            # 开始监控
            monitor.start()
            start_time = time.time()

            # 发送简单请求
            prompt = "Hello! Please respond with 'Hello, World!' in Chinese."
            print(f"\n📤 发送请求: {prompt}")

            response = self.model.generate_content(prompt)

            end_time = time.time()
            monitor.stop()

            # 计算响应时间
            response_time = end_time - start_time

            print(f"\n✅ API 调用成功!")
            print(f"📥 响应: {response.text}")
            print(f"⏱️  响应时间: {response_time:.2f} 秒")

            # 打印资源统计
            monitor.print_stats()

            return {
                'success': True,
                'response_time': response_time,
                'response_text': response.text,
                'stats': monitor.get_stats()
            }

        except Exception as e:
            monitor.stop()
            print(f"\n❌ 测试失败: {e}")
            return {'success': False, 'error': str(e)}

    def test_complex_query(self, monitor: ResourceMonitor) -> Dict:
        """
        测试复杂查询（模拟市场分析场景）

        Args:
            monitor: 资源监控器

        Returns:
            测试结果
        """
        if not self.enabled:
            return {'success': False, 'error': 'Gemini 未启用'}

        print("\n" + "="*80)
        print("测试 2: 复杂查询（市场分析场景）")
        print("="*80)

        try:
            # 开始监控
            monitor.start()
            start_time = time.time()

            # 发送复杂的市场分析请求
            prompt = """
你是一名资深的加密货币交易分析师。请分析以下市场数据：

当前价格: $45,230
24小时涨跌: +3.2%
成交量: $28.5B
RSI(14): 62.5
MACD: 正向交叉
布林带: 价格接近上轨

请提供：
1. 当前市场趋势判断
2. 关键支撑位和阻力位
3. 短期交易建议（做多/做空/观望）
4. 风险提示

请用中文简洁回答，不超过200字。
"""
            print(f"\n📤 发送复杂查询...")

            response = self.model.generate_content(prompt)

            end_time = time.time()
            monitor.stop()

            # 计算响应时间
            response_time = end_time - start_time

            print(f"\n✅ API 调用成功!")
            print(f"📥 响应长度: {len(response.text)} 字符")
            print(f"⏱️  响应时间: {response_time:.2f} 秒")
            print(f"\n响应内容:\n{response.text[:300]}...")

            # 打印资源统计
            monitor.print_stats()

            return {
                'success': True,
                'response_time': response_time,
                'response_length': len(response.text),
                'stats': monitor.get_stats()
            }

        except Exception as e:
            monitor.stop()
            print(f"\n❌ 测试失败: {e}")
            return {'success': False, 'error': str(e)}

    def test_multiple_calls(self, monitor: ResourceMonitor, count: int = 3) -> Dict:
        """
        测试多次连续调用

        Args:
            monitor: 资源监控器
            count: 调用次数

        Returns:
            测试结果
        """
        if not self.enabled:
            return {'success': False, 'error': 'Gemini 未启用'}

        print("\n" + "="*80)
        print(f"测试 3: 多次连续调用 (共 {count} 次)")
        print("="*80)

        results = []

        try:
            # 开始监控
            monitor.start()
            overall_start = time.time()

            for i in range(count):
                print(f"\n📤 第 {i+1}/{count} 次调用...")
                start_time = time.time()

                prompt = f"请用一句话介绍比特币的第 {i+1} 个特点。"
                response = self.model.generate_content(prompt)

                end_time = time.time()
                response_time = end_time - start_time

                print(f"✅ 响应时间: {response_time:.2f} 秒")
                print(f"📥 响应: {response.text[:100]}...")

                results.append({
                    'call_number': i + 1,
                    'response_time': response_time,
                    'response_length': len(response.text)
                })

                # 短暂延迟，避免请求过快
                if i < count - 1:
                    time.sleep(0.5)

            overall_end = time.time()
            monitor.stop()

            # 计算统计信息
            total_time = overall_end - overall_start
            avg_response_time = sum(r['response_time'] for r in results) / len(results)

            print(f"\n✅ 所有调用完成!")
            print(f"⏱️  总耗时: {total_time:.2f} 秒")
            print(f"⏱️  平均响应时间: {avg_response_time:.2f} 秒")

            # 打印资源统计
            monitor.print_stats()

            return {
                'success': True,
                'total_time': total_time,
                'avg_response_time': avg_response_time,
                'results': results,
                'stats': monitor.get_stats()
            }

        except Exception as e:
            monitor.stop()
            print(f"\n❌ 测试失败: {e}")
            return {'success': False, 'error': str(e)}


if __name__ == "__main__":
    print("="*80)
    print("🧪 Gemini API 性能测试")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Python 版本: {sys.version}")
    print(f"进程 PID: {os.getpid()}")
    print("="*80)

    # 初始化测试器
    tester = GeminiTester()

    if not tester.enabled:
        print("\n❌ Gemini 测试器未启用，请检查配置")
        print("\n配置说明:")
        print("1. 安装 SDK: pip install google-generativeai")
        print("2. 设置环境变量: export GEMINI_API_KEY=your_api_key")
        print("   或: export GOOGLE_API_KEY=your_api_key")
        sys.exit(1)

    # 存储所有测试结果
    all_results = []

    # 测试 1: 简单调用
    monitor1 = ResourceMonitor(interval=0.1)
    result1 = tester.test_simple_call(monitor1)
    all_results.append(('简单调用', result1))

    # 等待一下
    time.sleep(2)

    # 测试 2: 复杂查询
    monitor2 = ResourceMonitor(interval=0.1)
    result2 = tester.test_complex_query(monitor2)
    all_results.append(('复杂查询', result2))

    # 等待一下
    time.sleep(2)

    # 测试 3: 多次调用
    monitor3 = ResourceMonitor(interval=0.1)
    result3 = tester.test_multiple_calls(monitor3, count=3)
    all_results.append(('多次调用', result3))

    # 打印总结
    print("\n" + "="*80)
    print("📋 测试总结")
    print("="*80)

    for test_name, result in all_results:
        if result.get('success'):
            print(f"\n✅ {test_name}: 成功")
            if 'response_time' in result:
                print(f"   响应时间: {result['response_time']:.2f} 秒")
            if 'avg_response_time' in result:
                print(f"   平均响应时间: {result['avg_response_time']:.2f} 秒")
        else:
            print(f"\n❌ {test_name}: 失败 - {result.get('error', '未知错误')}")

    print("\n" + "="*80)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
