#!/usr/bin/env python3
"""
数据库Web可视化工具

功能：
- 在浏览器中查看数据库表
- 支持表格展示和数据筛选
- 自动生成统计信息
"""

import sqlite3
import json
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config.settings import settings as config

DB_PATH = config.DB_PATH


class DatabaseViewerHandler(BaseHTTPRequestHandler):
    """数据库查看器HTTP处理器"""

    def do_GET(self):
        """处理GET请求"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        query = parse_qs(parsed_path.query)

        if path == '/':
            self.serve_index()
        elif path == '/api/tables':
            self.serve_tables()
        elif path == '/api/table_data':
            table_name = query.get('table', [''])[0]
            limit = int(query.get('limit', ['100'])[0])
            self.serve_table_data(table_name, limit)
        elif path == '/api/stats':
            self.serve_stats()
        else:
            self.send_error(404)

    def serve_index(self):
        """提供主页面"""
        html = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Trading Bot 数据库查看器</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Arial, sans-serif;
            background: #f5f5f5;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 {
            color: #333;
            margin-bottom: 20px;
            padding-bottom: 10px;
            border-bottom: 3px solid #4CAF50;
        }
        .stats {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 20px;
        }
        .stat-card {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        .stat-card h3 {
            color: #666;
            font-size: 14px;
            margin-bottom: 10px;
        }
        .stat-card .value {
            color: #4CAF50;
            font-size: 24px;
            font-weight: bold;
        }
        .controls {
            background: white;
            padding: 20px;
            border-radius: 8px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }
        select, button {
            padding: 10px 15px;
            font-size: 14px;
            border: 1px solid #ddd;
            border-radius: 4px;
            margin-right: 10px;
        }
        button {
            background: #4CAF50;
            color: white;
            border: none;
            cursor: pointer;
        }
        button:hover { background: #45a049; }
        .table-container {
            background: white;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            overflow: hidden;
        }
        table {
            width: 100%;
            border-collapse: collapse;
        }
        th {
            background: #4CAF50;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
            position: sticky;
            top: 0;
        }
        td {
            padding: 10px 12px;
            border-bottom: 1px solid #eee;
        }
        tr:hover { background: #f9f9f9; }
        .loading {
            text-align: center;
            padding: 40px;
            color: #666;
        }
        .error {
            background: #ffebee;
            color: #c62828;
            padding: 15px;
            border-radius: 4px;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>📊 Trading Bot 数据库查看器</h1>

        <div id="stats" class="stats"></div>

        <div class="controls">
            <select id="tableSelect">
                <option value="">选择表...</option>
            </select>
            <select id="limitSelect">
                <option value="50">显示 50 条</option>
                <option value="100" selected>显示 100 条</option>
                <option value="500">显示 500 条</option>
                <option value="1000">显示 1000 条</option>
            </select>
            <button onclick="loadTableData()">加载数据</button>
            <button onclick="refreshStats()">刷新统计</button>
        </div>

        <div class="table-container">
            <div id="tableContent" class="loading">请选择一个表查看数据</div>
        </div>
    </div>

    <script>
        // 加载表列表
        async function loadTables() {
            try {
                const response = await fetch('/api/tables');
                const tables = await response.json();
                const select = document.getElementById('tableSelect');
                tables.forEach(table => {
                    const option = document.createElement('option');
                    option.value = table;
                    option.textContent = table;
                    select.appendChild(option);
                });
            } catch (error) {
                console.error('加载表列表失败:', error);
            }
        }

        // 加载统计信息
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const stats = await response.json();
                const statsDiv = document.getElementById('stats');
                statsDiv.innerHTML = Object.entries(stats).map(([key, value]) => `
                    <div class="stat-card">
                        <h3>${key}</h3>
                        <div class="value">${value.toLocaleString()}</div>
                    </div>
                `).join('');
            } catch (error) {
                console.error('加载统计信息失败:', error);
            }
        }

        // 加载表数据
        async function loadTableData() {
            const table = document.getElementById('tableSelect').value;
            const limit = document.getElementById('limitSelect').value;

            if (!table) {
                alert('请先选择一个表');
                return;
            }

            const content = document.getElementById('tableContent');
            content.innerHTML = '<div class="loading">加载中...</div>';

            try {
                const response = await fetch(`/api/table_data?table=${table}&limit=${limit}`);
                const data = await response.json();

                if (data.error) {
                    content.innerHTML = `<div class="error">${data.error}</div>`;
                    return;
                }

                if (data.rows.length === 0) {
                    content.innerHTML = '<div class="loading">表中没有数据</div>';
                    return;
                }

                // 生成表格
                let html = '<table><thead><tr>';
                data.columns.forEach(col => {
                    html += `<th>${col}</th>`;
                });
                html += '</tr></thead><tbody>';

                data.rows.forEach(row => {
                    html += '<tr>';
                    row.forEach(cell => {
                        html += `<td>${cell !== null ? cell : '<i>NULL</i>'}</td>`;
                    });
                    html += '</tr>';
                });

                html += '</tbody></table>';
                content.innerHTML = html;
            } catch (error) {
                content.innerHTML = `<div class="error">加载失败: ${error.message}</div>`;
            }
        }

        function refreshStats() {
            loadStats();
        }

        // 页面加载时初始化
        window.onload = () => {
            loadTables();
            loadStats();
        };
    </script>
</body>
</html>
        """
        self.send_response(200)
        self.send_header('Content-type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(html.encode('utf-8'))

    def serve_tables(self):
        """返回所有表名"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name")
            tables = [row[0] for row in cursor.fetchall()]
            conn.close()

            self.send_json(tables)
        except Exception as e:
            self.send_json({'error': str(e)})

    def serve_table_data(self, table_name, limit):
        """返回表数据"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # 获取列名
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [row[1] for row in cursor.fetchall()]

            # 获取数据
            cursor.execute(f"SELECT * FROM {table_name} ORDER BY id DESC LIMIT {limit}")
            rows = cursor.fetchall()
            conn.close()

            self.send_json({
                'columns': columns,
                'rows': rows
            })
        except Exception as e:
            self.send_json({'error': str(e)})

    def serve_stats(self):
        """返回统计信息"""
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            stats = {}

            # 获取各表记录数
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]

            for table in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                stats[f"{table} 记录数"] = count

            # 数据库大小
            cursor.execute("SELECT page_count * page_size as size FROM pragma_page_count(), pragma_page_size()")
            size = cursor.fetchone()[0]
            stats["数据库大小 (MB)"] = round(size / 1024 / 1024, 2)

            conn.close()

            self.send_json(stats)
        except Exception as e:
            self.send_json({'error': str(e)})

    def send_json(self, data):
        """发送JSON响应"""
        self.send_response(200)
        self.send_header('Content-type', 'application/json; charset=utf-8')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))

    def log_message(self, format, *args):
        """禁用访问日志"""
        pass


def main():
    """启动Web服务器"""
    port = 8888
    server = HTTPServer(('0.0.0.0', port), DatabaseViewerHandler)

    print("=" * 60)
    print("📊 Trading Bot 数据库查看器")
    print("=" * 60)
    print(f"数据库: {DB_PATH}")
    print(f"服务地址: http://localhost:{port}")
    print(f"服务地址: http://127.0.0.1:{port}")
    print("=" * 60)
    print("按 Ctrl+C 停止服务")
    print("=" * 60)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n\n服务已停止")
        server.shutdown()


if __name__ == "__main__":
    main()
