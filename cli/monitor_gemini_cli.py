#!/usr/bin/env python3
"""
监控 Gemini CLI 运行时的资源使用情况
"""

import os
import sys
import time
import psutil
import subprocess
import threading
from datetime import datetime

class ProcessMonitor:
    """进程资源监控器"""

    def __init__(self, pid, interval=0.1):
        self.pid = pid
        self.interval = interval
        self.monitoring = False
        self.samples = []

    def start(self):
        """开始监控"""
        self.monitoring = True
        self.samples = []
        self.thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.thread.start()
        print(f"✅ 开始监控进程 {self.pid}")

    def stop(self):
        """停止监控"""
        self.monitoring = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2)
        print(f"✅ 停止监控 (采集 {len(self.samples)} 个样本)")

    def _monitor_loop(self):
        """监控循环"""
        try:
            process = psutil.Process(self.pid)
        except psutil.NoSuchProcess:
            print(f"⚠️ 进程 {self.pid} 不存在")
            return

        while self.monitoring:
            try:
                # 检查进程是否还存在
                if not process.is_running():
                    break

                sample = {
                    'timestamp': time.time(),
                    'cpu_percent': process.cpu_percent(interval=None),
                    'memory_mb': process.memory_info().rss / 1024 / 1024,
                    'memory_percent': process.memory_percent(),
                    'threads': process.num_threads(),
                    'system_cpu': psutil.cpu_percent(interval=None),
                    'system_memory': psutil.virtual_memory().percent,
                }

                self.samples.append(sample)
                time.sleep(self.interval)

            except (psutil.NoSuchProcess, psutil.AccessDenied):
                break
            except Exception as e:
                print(f"⚠️ 监控错误: {e}")
                break

    def print_stats(self):
        """打印统计信息"""
        if not self.samples:
            print("⚠️ 没有采集到数据")
            return

        cpu_values = [s['cpu_percent'] for s in self.samples]
        memory_values = [s['memory_mb'] for s in self.samples]
        sys_cpu_values = [s['system_cpu'] for s in self.samples]
        sys_mem_values = [s['system_memory'] for s in self.samples]

        duration = self.samples[-1]['timestamp'] - self.samples[0]['timestamp']

        print("\n" + "="*80)
        print("📊 资源使用统计")
        print("="*80)
        print(f"\n⏱️  监控时长: {duration:.2f} 秒")
        print(f"📈 采样数量: {len(self.samples)} 个")

        print("\n🔹 进程资源:")
        print(f"  CPU: 最小={min(cpu_values):.1f}% | "
              f"平均={sum(cpu_values)/len(cpu_values):.1f}% | "
              f"最大={max(cpu_values):.1f}%")
        print(f"  内存: 最小={min(memory_values):.1f}MB | "
              f"平均={sum(memory_values)/len(memory_values):.1f}MB | "
              f"最大={max(memory_values):.1f}MB")
        print(f"  线程数: {self.samples[-1]['threads']}")

        print("\n🔹 系统资源:")
        print(f"  CPU: 最小={min(sys_cpu_values):.1f}% | "
              f"平均={sum(sys_cpu_values)/len(sys_cpu_values):.1f}% | "
              f"最大={max(sys_cpu_values):.1f}%")
        print(f"  内存: 最小={min(sys_mem_values):.1f}% | "
              f"平均={sum(sys_mem_values)/len(sys_mem_values):.1f}% | "
              f"最大={max(sys_mem_values):.1f}%")

        # 警告
        if max(cpu_values) > 80:
            print("\n⚠️  警告: 进程CPU占用峰值超过80%")
        if max(sys_cpu_values) > 90:
            print("\n⚠️  警告: 系统CPU占用峰值超过90%")
        if max(memory_values) > 1000:
            print("\n⚠️  警告: 进程内存占用峰值超过1GB")


if __name__ == "__main__":
    print("="*80)
    print("🧪 Gemini CLI 资源监控")
    print("="*80)
    print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)

    # 测试命令
    test_prompt = "Hello, please respond with 'Hello World' in Chinese"

    print(f"\n📤 测试提示: {test_prompt}")
    print("🚀 启动 gemini CLI...")

    # 启动 gemini CLI 进程
    process = subprocess.Popen(
        ['gemini', test_prompt],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True
    )

    print(f"✅ 进程已启动 (PID: {process.pid})")

    # 开始监控
    monitor = ProcessMonitor(process.pid, interval=0.1)
    monitor.start()

    # 等待进程完成（最多60秒）
    try:
        stdout, stderr = process.communicate(timeout=60)
        print(f"\n✅ 进程已完成 (返回码: {process.returncode})")

        if stdout:
            print(f"\n📥 输出:\n{stdout[:500]}")
        if stderr:
            print(f"\n⚠️ 错误:\n{stderr[:500]}")

    except subprocess.TimeoutExpired:
        print("\n⚠️ 进程超时（60秒），正在终止...")
        process.kill()
        stdout, stderr = process.communicate()

    finally:
        monitor.stop()
        monitor.print_stats()

    print("\n" + "="*80)
    print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*80)
