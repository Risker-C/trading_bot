# Feature Development Standard Process (功能开发标准流程)

## 命令说明
这是一个强制执行的标准化功能开发流程，适用于所有新功能开发和功能增强。

## 触发条件
当用户提出以下类型的需求时，**自动且强制**使用此流程：
- 新增功能模块
- 功能增强
- 系统集成
- 任何涉及代码修改的需求

## 执行流程

### 阶段1：需求分析与规划 (MANDATORY)

1. **探索现有代码结构**
   - 使用Task工具（subagent_type=Explore）探索相关代码
   - 理解现有架构和模块关系
   - 识别需要修改的文件

2. **制定实施方案**
   - 分析技术实现路径
   - 识别潜在风险和依赖
   - 确定需要修改的配置项

3. **创建任务清单**
   - 使用TodoWrite工具创建详细的任务清单
   - 任务必须包含：
     * 配置文件修改
     * 核心模块开发
     * 主程序集成
     * 文档编写
     * 测试用例编写
     * 测试执行
     * 服务重启验证
     * 代码提交和推送

### 阶段2：开发实施 (MANDATORY)

4. **修改配置文件**
   - 在 `config.py` 中添加新功能的配置项
   - 更新配置验证函数
   - 确保配置项有清晰的注释说明

5. **开发核心模块**
   - 创建新的模块文件（如果需要）
   - 实现核心功能逻辑
   - 遵循现有代码风格和架构模式
   - **如果是新功能，必须添加日志记录**：
     * 使用 `get_logger()` 创建logger
     * 在关键操作处添加INFO级别日志
     * 在错误处理处添加ERROR级别日志
     * 在调试信息处添加DEBUG级别日志

6. **集成到主程序**
   - 在主程序（如bot.py、main.py）中集成新功能
   - 确保不破坏现有功能
   - 处理异常情况

7. **修复相关Bug**
   - 检查并修复引入的bug
   - 检查并修复发现的现有bug

### 阶段3：文档编写 (MANDATORY)

8. **创建功能说明文档**
   - **必须**在 `docs/` 目录下创建文档
   - 文档命名规范：`{功能名称}.md`（使用小写和下划线）
   - **文档格式要求**：
     ```markdown
     # {功能名称}功能说明文档

     ## 概述
     [功能简介，1-2段]

     ## 功能特性
     [列出主要功能点]

     ## 配置说明
     ### 配置文件位置
     ### 配置项详解
     [每个配置项的说明]

     ## 使用方法
     [详细的使用步骤]

     ## 技术实现
     [核心模块和数据流程]

     ## 故障排查
     [常见问题和解决方法]

     ## 性能优化
     [优化建议]

     ## 扩展开发
     [如何扩展此功能]

     ## 最佳实践
     [使用建议]

     ## 更新日志
     [版本历史]

     ## 相关文档
     [链接到其他相关文档]
     ```

9. **更新配置说明**
   - 如果修改了配置，更新相关配置文档

### 阶段4：测试用例编写 (MANDATORY)

10. **创建测试用例**
    - **必须**在 `scripts/` 目录下创建测试文件
    - 测试文件命名规范：`test_{功能名称}.py`（使用小写和下划线）
    - **测试用例格式要求**：
      ```python
      #!/usr/bin/env python3
      """
      {功能名称}测试脚本

      测试内容：
      1. [测试项1]
      2. [测试项2]
      ...
      """

      import sys
      import os
      from datetime import datetime

      # 添加项目根目录到路径
      sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

      # 导入必要的模块
      import config
      from logger_utils import get_logger

      logger = get_logger("test_{功能名称}")


      class Test{功能名称}:
          """测试类"""

          def __init__(self):
              self.passed = 0
              self.failed = 0
              self.total = 0

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


      def test_config_validation():
          """测试1: 配置验证"""
          # 测试代码
          pass


      def test_core_functionality():
          """测试2: 核心功能"""
          # 测试代码
          pass


      def main():
          """主测试函数"""
          print("\n" + "="*60)
          print("{功能名称}测试")
          print("="*60)
          print(f"开始时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
          print("="*60)

          tester = Test{功能名称}()

          # 运行所有测试
          tester.run_test("配置验证", test_config_validation)
          tester.run_test("核心功能", test_core_functionality)
          # ... 更多测试

          # 打印摘要
          success = tester.print_summary()

          print(f"结束时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

          # 返回退出码
          sys.exit(0 if success else 1)


      if __name__ == "__main__":
          main()
      ```

11. **添加执行权限**
    - 使用 `chmod +x scripts/test_{功能名称}.py` 添加执行权限

### 阶段5：测试执行 (MANDATORY)

12. **运行本次测试用例**
    - 执行新创建的测试用例：`python3 scripts/test_{功能名称}.py`
    - 确保所有测试通过
    - 如果测试失败，修复问题后重新测试

13. **运行全部测试用例**
    - 执行项目的主测试套件：`python3 test_all.py`（如果存在）
    - 或者运行所有测试脚本
    - 确保没有破坏现有功能

14. **将测试用例添加到主测试套件**
    - 如果存在 `test_all.py`，将新测试用例导入并添加到测试列表
    - 更新测试文档，记录新增的测试用例
    - 示例：
      ```python
      # 在 test_all.py 中添加
      from scripts.test_{功能名称} import main as test_{功能名称}_main

      # 在测试列表中添加
      tests = [
          # ... 现有测试
          ("test_{功能名称}", test_{功能名称}_main),
      ]
      ```

### 阶段6：服务验证 (MANDATORY)

15. **停止当前服务**
    - 检查是否有服务在运行
    - 使用 `./stop_bot.sh` 或 `kill` 命令停止服务

16. **重启服务**
    - 使用 `./start_bot.sh` 启动服务
    - 记录启动日志

17. **验证功能**
    - 查看日志确认新功能已启动
    - 检查是否有错误日志
    - 验证功能是否按预期工作
    - 等待至少1-2分钟观察运行状态

### 阶段7：总结与文档 (MANDATORY)

18. **生成完成报告**
    - 总结完成的功能
    - 列出修改的文件
    - 列出新增的文件
    - 提供测试结果
    - 提供服务运行状态
    - 提供使用说明
    - 提供后续建议

19. **更新CHANGELOG.md**
    - **必须**将完成报告写入 `CHANGELOG.md` 文件
    - 在文件开头添加新的条目（最新的在最上面）
    - **CHANGELOG格式要求**：
      ```markdown
      ## [YYYY-MM-DD] {功能/修复简短描述}

      ### 类型
      - 🎉 新功能 / 🐛 Bug修复 / ⚡ 性能优化 / 📝 文档更新 / 🔧 配置调整

      ### 功能概述
      [1-2段功能简介]

      ### 修改内容

      #### 修改的文件
      - `文件路径`: 修改说明
      - `文件路径`: 修改说明

      #### 新增的文件
      - `文件路径`: 文件说明
      - `文件路径`: 文件说明

      ### 技术细节

      #### 核心实现
      - 实现细节1
      - 实现细节2

      #### 配置项（如果有）
      ```python
      CONFIG_NAME = value  # 说明
      ```

      ### 测试结果
      - ✅ 测试用例: 通过/失败
      - ✅ 服务验证: 正常运行

      ### 影响范围
      - 影响的模块/功能
      - 兼容性说明

      ### 使用说明
      [如何使用新功能或修复后的功能]

      ### 后续建议
      - 建议1
      - 建议2

      ---
      ```
    - 确保格式规范，便于后续查阅

### 阶段8：代码提交 (MANDATORY)

20. **检查Git状态**
    - 运行 `git status` 查看修改的文件
    - 确认所有必要的文件都已修改
    - **确保CHANGELOG.md已更新并包含在修改列表中**

21. **添加文件到Git**
    - 添加所有修改和新增的文件
    - 确保文档、测试用例和CHANGELOG.md都已添加

22. **创建提交**
    - 使用规范的提交信息格式：
      ```
      feat: {功能简短描述}

      功能特性：
      - {特性1}
      - {特性2}

      技术实现：
      - {实现细节1}
      - {实现细节2}

      文档和测试：
      - 新增 docs/{功能名称}.md 功能说明文档
      - 新增 scripts/test_{功能名称}.py 测试用例
      - 更新 CHANGELOG.md 记录本次修改
      - 所有测试通过

      🤖 Generated with [Claude Code](https://claude.com/claude-code)

      Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>
      ```

23. **推送到远程仓库**
    - 执行 `git push` 推送代码
    - 确认推送成功

## 质量标准

### 代码质量
- [ ] 代码遵循现有风格
- [ ] 有适当的错误处理
- [ ] 有清晰的注释
- [ ] 新功能有日志记录

### 文档质量
- [ ] 文档结构完整
- [ ] 文档内容清晰
- [ ] 有使用示例
- [ ] 有故障排查指南

### 测试质量
- [ ] 测试覆盖核心功能
- [ ] 测试用例结构规范
- [ ] 所有测试通过
- [ ] 测试已添加到主测试套件

### 部署质量
- [ ] 服务成功重启
- [ ] 功能正常运行
- [ ] 无错误日志
- [ ] 代码已提交并推送

## 注意事项

1. **强制执行**：此流程是强制性的，不可跳过任何步骤
2. **文档优先**：文档和测试用例与代码同等重要
3. **测试驱动**：确保测试通过后才能提交代码
4. **服务验证**：必须验证服务正常运行后才能完成
5. **日志记录**：新功能必须有完善的日志记录
6. **格式规范**：严格遵守文档和测试用例的格式要求
7. **目录规范**：文档必须放在docs/，测试必须放在scripts/
8. **主测试集成**：新测试用例必须集成到主测试套件

## 失败处理

如果任何阶段失败：
1. 立即停止后续步骤
2. 分析失败原因
3. 修复问题
4. 从失败的步骤重新开始
5. 不允许跳过失败的步骤

## 使用示例

用户输入：
```
新增一个定时备份功能，每天凌晨2点自动备份数据库
```

系统响应：
```
我将按照标准功能开发流程（feature-dev）来实现这个功能。

阶段1：需求分析与规划
[开始探索代码结构...]
[创建任务清单...]

阶段2：开发实施
[修改配置文件...]
[开发核心模块...]
...
```

## 版本历史

- v1.0.0 (2024-12-15): 初始版本，基于状态监控功能开发经验创建
