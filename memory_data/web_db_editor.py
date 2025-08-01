#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Web版SQLite数据库编辑器
提供Web界面来编辑 memory.db 数据库
"""

from flask import Flask, render_template, render_template_string, request, jsonify, redirect, url_for, make_response
import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # 确保JSON响应支持中文
DB_PATH = "d:\\browser-use-self\\memory_data\\memory.db"

class WebDatabaseEditor:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path
        
    def connect(self):
        """连接数据库"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
        return sqlite3.connect(self.db_path)
    
    def get_tables(self):
        """获取所有表"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            result = []
            for table_name, in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                result.append({"name": table_name, "count": count})
            return result
    
    def get_table_structure(self, table_name: str):
        """获取表结构"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            result = []
            for col in columns:
                cid, name, col_type, notnull, default, pk = col
                result.append({
                    "name": name,
                    "type": col_type,
                    "notnull": bool(notnull),
                    "default": default,
                    "primary_key": bool(pk)
                })
            return result
    
    def get_records(self, table_name: str, limit: int = 10, offset: int = 0):
        """获取记录"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 获取总数
            cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
            total = cursor.fetchone()[0]
            
            # 获取记录
            cursor.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
            records = cursor.fetchall()
            
            # 获取列名
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            result = []
            for record in records:
                record_dict = {}
                for col_name, value in zip(columns, record):
                    # 处理JSON字段
                    if col_name in ['execution_steps', 'similarity_keywords'] and value:
                        try:
                            parsed_json = json.loads(value)
                            record_dict[col_name] = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                        except:
                            record_dict[col_name] = value
                    else:
                        record_dict[col_name] = value
                result.append(record_dict)
            
            return {
                "records": result,
                "columns": columns,
                "total": total,
                "limit": limit,
                "offset": offset
            }
    
    def get_record_by_id(self, table_name: str, record_id: str):
        """根据ID获取记录"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 获取列名
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            cursor.execute(f"SELECT * FROM {table_name} WHERE id = ?", (record_id,))
            record = cursor.fetchone()
            
            if not record:
                return None
            
            record_dict = {}
            for col_name, value in zip(columns, record):
                # 处理JSON字段
                if col_name in ['execution_steps', 'similarity_keywords'] and value:
                    try:
                        parsed_json = json.loads(value)
                        record_dict[col_name] = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                    except:
                        record_dict[col_name] = value
                else:
                    record_dict[col_name] = value
            
            return record_dict
    
    def update_record(self, table_name: str, record_id: str, updates: Dict[str, Any]):
        """更新记录"""
        if not updates:
            return False
            
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 处理JSON字段
            processed_updates = {}
            for key, value in updates.items():
                if key in ['execution_steps', 'similarity_keywords']:
                    if isinstance(value, str) and value.strip():
                        # 如果是字符串，先验证是否为有效JSON
                        try:
                            json.loads(value)  # 验证JSON格式
                            processed_updates[key] = value  # 直接使用字符串
                        except json.JSONDecodeError:
                            raise ValueError(f"字段 {key} 的JSON格式无效")
                    elif isinstance(value, (list, dict)):
                        # 如果是对象，转换为JSON字符串
                        processed_updates[key] = json.dumps(value, ensure_ascii=False)
                    else:
                        processed_updates[key] = value
                else:
                    processed_updates[key] = value
            
            # 构建更新语句
            set_clause = ", ".join([f"{col} = ?" for col in processed_updates.keys()])
            values = list(processed_updates.values()) + [record_id]
            
            query = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
            
            try:
                cursor.execute(query, values)
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                raise e
    
    def delete_record(self, table_name: str, record_id: str):
        """删除记录"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
                conn.commit()
                return cursor.rowcount > 0
            except Exception as e:
                raise e
    
    def search_records(self, table_name: str, column: str, keyword: str):
        """搜索记录"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            query = f"SELECT * FROM {table_name} WHERE {column} LIKE ?"
            cursor.execute(query, (f"%{keyword}%",))
            records = cursor.fetchall()
            
            # 获取列名
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = [col[1] for col in cursor.fetchall()]
            
            result = []
            for record in records:
                record_dict = {}
                for col_name, value in zip(columns, record):
                    if col_name in ['execution_steps', 'similarity_keywords'] and value:
                        try:
                            parsed_json = json.loads(value)
                            record_dict[col_name] = json.dumps(parsed_json, ensure_ascii=False, indent=2)
                        except:
                            record_dict[col_name] = value
                    else:
                        record_dict[col_name] = value
                result.append(record_dict)
            
            return result

# 创建编辑器实例
editor = WebDatabaseEditor()

@app.route('/')
def index():
    """主页"""
    try:
        tables = editor.get_tables()
        response = make_response(render_template_string(INDEX_TEMPLATE, tables=tables))
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as e:
        return f"错误: {e}", 500

@app.route('/table/<table_name>')
def view_table(table_name):
    """查看表"""
    try:
        limit = int(request.args.get('limit', 10))
        offset = int(request.args.get('offset', 0))
        
        structure = editor.get_table_structure(table_name)
        data = editor.get_records(table_name, limit, offset)
        
        response = make_response(render_template_string(TABLE_TEMPLATE, 
                                    table_name=table_name,
                                    structure=structure,
                                    data=data))
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as e:
        return f"错误: {e}", 500

@app.route('/record/<table_name>/<record_id>')
def view_record(table_name, record_id):
    """查看记录"""
    try:
        record = editor.get_record_by_id(table_name, record_id)
        if not record:
            return "记录不存在", 404
        
        structure = editor.get_table_structure(table_name)
        
        response = make_response(render_template_string(RECORD_TEMPLATE,
                                    table_name=table_name,
                                    record_id=record_id,
                                    record=record,
                                    structure=structure))
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as e:
        return f"错误: {e}", 500

@app.route('/api/update_record', methods=['POST'])
def api_update_record():
    """更新记录API"""
    try:
        data = request.json
        table_name = data['table_name']
        record_id = data['record_id']
        updates = data['updates']
        
        success = editor.update_record(table_name, record_id, updates)
        
        return jsonify({
            "success": success,
            "message": "更新成功" if success else "记录不存在"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/api/delete_record', methods=['POST'])
def api_delete_record():
    """删除记录API"""
    try:
        data = request.json
        table_name = data['table_name']
        record_id = data['record_id']
        
        success = editor.delete_record(table_name, record_id)
        
        return jsonify({
            "success": success,
            "message": "删除成功" if success else "记录不存在"
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": str(e)
        }), 500

@app.route('/search/<table_name>')
def search_table(table_name):
    """搜索表"""
    try:
        column = request.args.get('column', 'question')
        keyword = request.args.get('keyword', '')
        
        if not keyword:
            return redirect(url_for('view_table', table_name=table_name))
        
        results = editor.search_records(table_name, column, keyword)
        structure = editor.get_table_structure(table_name)
        
        response = make_response(render_template_string(SEARCH_TEMPLATE,
                                    table_name=table_name,
                                    column=column,
                                    keyword=keyword,
                                    results=results,
                                    structure=structure))
        response.headers['Content-Type'] = 'text/html; charset=utf-8'
        return response
    except Exception as e:
        return f"错误: {e}", 500

# HTML模板
INDEX_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>数据库编辑器</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        .table-list { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin-top: 20px; }
        .table-card { background: #f8f9fa; padding: 20px; border-radius: 8px; border: 1px solid #dee2e6; transition: transform 0.2s; }
        .table-card:hover { transform: translateY(-2px); box-shadow: 0 4px 15px rgba(0,0,0,0.1); }
        .table-name { font-size: 1.2em; font-weight: bold; color: #007bff; margin-bottom: 10px; }
        .table-count { color: #6c757d; }
        .btn { display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-top: 10px; }
        .btn:hover { background: #0056b3; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🗄️ SQLite数据库编辑器</h1>
        <p>数据库路径: <code>{{ "d:\\browser-use-self\\memory_data\\memory.db" }}</code></p>
        
        <div class="table-list">
            {% for table in tables %}
            <div class="table-card">
                <div class="table-name">📊 {{ table.name }}</div>
                <div class="table-count">{{ table.count }} 条记录</div>
                <a href="/table/{{ table.name }}" class="btn">查看表</a>
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
'''

TABLE_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>表: {{ table_name }}</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        .nav { margin-bottom: 20px; }
        .btn { display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px; }
        .btn:hover { background: #0056b3; }
        .btn-secondary { background: #6c757d; }
        .btn-secondary:hover { background: #545b62; }
        .search-form { margin: 20px 0; padding: 15px; background: #f8f9fa; border-radius: 5px; }
        .search-form input, .search-form select { padding: 8px; margin: 5px; border: 1px solid #ddd; border-radius: 4px; }
        .table-wrapper { overflow-x: auto; margin-top: 20px; }
        table { width: 100%; border-collapse: collapse; min-width: 800px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; white-space: nowrap; }
        th { background-color: #f8f9fa; font-weight: bold; }
        tr:hover { background-color: #f5f5f5; }
        .json-field { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .pagination { margin-top: 20px; text-align: center; }
        .pagination a { display: inline-block; padding: 8px 12px; margin: 0 4px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; }
        .pagination a:hover { background: #0056b3; }
        .pagination .current { background: #6c757d; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav">
            <a href="/" class="btn btn-secondary">← 返回首页</a>
        </div>
        
        <h1>📋 表: {{ table_name }}</h1>
        
        <div class="search-form">
            <form action="/search/{{ table_name }}" method="get">
                <select name="column">
                    {% for col in structure %}
                    <option value="{{ col.name }}">{{ col.name }}</option>
                    {% endfor %}
                </select>
                <input type="text" name="keyword" placeholder="搜索关键词..." required>
                <button type="submit" class="btn">🔍 搜索</button>
            </form>
        </div>
        
        <p>共 {{ data.total }} 条记录，显示第 {{ data.offset + 1 }} - {{ data.offset + data.records|length }} 条</p>
        
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    {% for col in data.columns %}
                    <th>{{ col }}</th>
                    {% endfor %}
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                {% for record in data.records %}
                <tr>
                    {% for col in data.columns %}
                    <td>
                        {% if col in ['execution_steps', 'similarity_keywords'] and record[col] %}
                            <div class="json-field" title="{{ record[col]|string }}">{{ record[col]|string|truncate(50) }}</div>
                        {% elif col == 'result' and record[col] and record[col]|string|length > 100 %}
                            <div title="{{ record[col] }}">{{ record[col]|string|truncate(100) }}</div>
                        {% else %}
                            {{ record[col] }}
                        {% endif %}
                    </td>
                    {% endfor %}
                    <td>
                        <a href="/record/{{ table_name }}/{{ record.id }}" class="btn">查看/编辑</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        </div>
        
        <div class="pagination">
            {% if data.offset > 0 %}
                <a href="?offset={{ data.offset - data.limit }}&limit={{ data.limit }}">← 上一页</a>
            {% endif %}
            
            {% if data.offset + data.limit < data.total %}
                <a href="?offset={{ data.offset + data.limit }}&limit={{ data.limit }}">下一页 →</a>
            {% endif %}
        </div>
    </div>
</body>
</html>
'''

RECORD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>记录: {{ record_id }}</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1000px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        .nav { margin-bottom: 20px; }
        .btn { display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px; border: none; cursor: pointer; }
        .btn:hover { background: #0056b3; }
        .btn-secondary { background: #6c757d; }
        .btn-secondary:hover { background: #545b62; }
        .btn-danger { background: #dc3545; }
        .btn-danger:hover { background: #c82333; }
        .field { margin-bottom: 20px; padding: 15px; border: 1px solid #ddd; border-radius: 5px; }
        .field-name { font-weight: bold; color: #007bff; margin-bottom: 5px; }
        .field-type { font-size: 0.9em; color: #6c757d; margin-bottom: 10px; }
        .field-value { background: #f8f9fa; padding: 10px; border-radius: 4px; min-height: 20px; }
        textarea, input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; }
        textarea { min-height: 100px; resize: vertical; }
        .json-field { font-family: monospace; white-space: pre-wrap; }
        .actions { margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; }
        /* 全屏弹窗样式 */
        .modal-overlay {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.5);
            display: flex;
            justify-content: center;
            align-items: center;
            z-index: 9999;
        }
        .modal-content {
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
            max-width: 500px;
            width: 90%;
            text-align: center;
            position: relative;
        }
        .modal-content h3 {
            margin: 0 0 20px 0;
            color: #333;
        }
        .modal-content p {
            margin: 0 0 20px 0;
            font-size: 16px;
            line-height: 1.5;
        }
        .modal-buttons {
            display: flex;
            justify-content: center;
            gap: 10px;
        }
        .modal-btn {
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            font-size: 14px;
            min-width: 80px;
        }
        .modal-btn-primary {
            background: #007bff;
            color: white;
        }
        .modal-btn-primary:hover {
            background: #0056b3;
        }
        .modal-btn-secondary {
            background: #6c757d;
            color: white;
        }
        .modal-btn-secondary:hover {
            background: #545b62;
        }
        .success-modal .modal-content {
            border-left: 5px solid #28a745;
        }
        .error-modal .modal-content {
            border-left: 5px solid #dc3545;
        }
        .message { padding: 10px; margin: 10px 0; border-radius: 4px; }
        .success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav">
            <a href="/table/{{ table_name }}" class="btn btn-secondary">← 返回表</a>
        </div>
        
        <h1>📋 记录详情: {{ record_id }}</h1>
        
        <div id="message"></div>
        
        <form id="updateForm">
            {% for col in structure %}
            <div class="field">
                <div class="field-name">{{ col.name }}</div>
                <div class="field-type">{{ col.type }}{% if col.primary_key %} (主键){% endif %}{% if col.notnull %} (必填){% endif %}</div>
                <div class="field-value">
                    {% if col.name == 'id' %}
                        <input type="text" name="{{ col.name }}" value="{{ record[col.name] }}" readonly>
                    {% elif col.name in ['execution_steps', 'similarity_keywords'] %}
                        <textarea name="{{ col.name }}" placeholder="JSON格式">{% if record[col.name] %}{{ record[col.name]|safe }}{% endif %}</textarea>
                    {% elif col.name == 'result' %}
                        <textarea name="{{ col.name }}">{{ record[col.name] or '' }}</textarea>
                    {% else %}
                        <input type="text" name="{{ col.name }}" value="{{ record[col.name] or '' }}">
                    {% endif %}
                </div>
            </div>
            {% endfor %}
        </form>
        
        <div class="actions">
            <button onclick="updateRecord()" class="btn">💾 保存更改</button>
            <button onclick="deleteRecord()" class="btn btn-danger">🗑️ 删除记录</button>
        </div>
    </div>
    
    <script>
        function showMessage(text, type) {
            // 创建全屏弹窗
            const modalOverlay = document.createElement('div');
            modalOverlay.className = `modal-overlay ${type}-modal`;
            
            const modalContent = document.createElement('div');
            modalContent.className = 'modal-content';
            
            const title = type === 'success' ? '操作成功' : '操作失败';
            const icon = type === 'success' ? '✅' : '❌';
            
            modalContent.innerHTML = `
                <h3>${icon} ${title}</h3>
                <p>${text}</p>
                <div class="modal-buttons">
                    <button class="modal-btn modal-btn-primary" onclick="closeModal()">确定</button>
                </div>
            `;
            
            modalOverlay.appendChild(modalContent);
            document.body.appendChild(modalOverlay);
            
            // 点击遮罩层关闭弹窗
            modalOverlay.addEventListener('click', function(e) {
                if (e.target === modalOverlay) {
                    closeModal();
                }
            });
            
            // 自动关闭（可选）
            setTimeout(() => {
                if (document.body.contains(modalOverlay)) {
                    closeModal();
                }
            }, 5000);
        }
        
        function closeModal() {
            const modal = document.querySelector('.modal-overlay');
            if (modal) {
                modal.remove();
            }
        }
        
        // 存储原始值用于比较
        let originalValues = {};
        
        // 页面加载时保存原始值
        document.addEventListener('DOMContentLoaded', function() {
            const form = document.getElementById('updateForm');
            const formData = new FormData(form);
            for (let [key, value] of formData.entries()) {
                if (key != 'id') {
                    originalValues[key] = value;
                }
            }
            console.log('原始值已保存:', originalValues);
        });
        
        function updateRecord() {
            console.log('updateRecord 函数被调用');
            const form = document.getElementById('updateForm');
            const formData = new FormData(form);
            const updates = {};
            let hasChanges = false;
            
            for (let [key, value] of formData.entries()) {
                if (key != 'id') {
                    // 检查是否有实际更改
                    if (originalValues[key] !== value) {
                        hasChanges = true;
                        console.log(`字段 ${key} 已更改: "${originalValues[key]}" -> "${value}"`);
                        
                        // 处理JSON字段
                        if (['execution_steps', 'similarity_keywords'].includes(key)) {
                            if (value.trim()) {
                                try {
                                    // 验证JSON格式但保持为字符串发送
                                    JSON.parse(value);
                                    updates[key] = value;
                                } catch (e) {
                                    showMessage(`字段 ${key} 的JSON格式无效: ${e.message}`, 'error');
                                    return;
                                }
                            } else {
                                updates[key] = '';
                            }
                        } else {
                            updates[key] = value;
                        }
                    }
                }
            }
            
            console.log('检测到的更改:', updates);
            
            // 检查是否有实际更改
            if (!hasChanges || Object.keys(updates).length === 0) {
                showMessage('没有检测到任何更改', 'error');
                return;
            }
            
            fetch('/api/update_record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    table_name: '{{ table_name }}',
                    record_id: '{{ record_id }}',
                    updates: updates
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('记录更新成功！', 'success');
                } else {
                    showMessage('更新失败: ' + data.message, 'error');
                }
            })
            .catch(error => {
                showMessage('更新失败: ' + error, 'error');
            });
        }
        
        function deleteRecord() {
            if (!confirm('确认删除此记录？此操作不可撤销！')) {
                return;
            }
            
            fetch('/api/delete_record', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    table_name: '{{ table_name }}',
                    record_id: '{{ record_id }}'
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('记录删除成功！', 'success');
                    setTimeout(() => {
                        window.location.href = '/table/{{ table_name }}';
                    }, 2000);
                } else {
                    showMessage('删除失败: ' + data.message, 'error');
                }
            })
            .catch(error => {
                showMessage('删除失败: ' + error, 'error');
            });
        }
    </script>
</body>
</html>
'''

SEARCH_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>搜索结果</title>
    <meta charset="utf-8">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1400px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; border-bottom: 2px solid #007bff; padding-bottom: 10px; }
        .nav { margin-bottom: 20px; }
        .btn { display: inline-block; padding: 8px 16px; background: #007bff; color: white; text-decoration: none; border-radius: 4px; margin-right: 10px; }
        .btn:hover { background: #0056b3; }
        .btn-secondary { background: #6c757d; }
        .btn-secondary:hover { background: #545b62; }
        .search-info { background: #e7f3ff; padding: 15px; border-radius: 5px; margin-bottom: 20px; }
        .table-wrapper { overflow-x: auto; margin-top: 20px; }
        table { width: 100%; border-collapse: collapse; min-width: 800px; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; white-space: nowrap; }
        th { background-color: #f8f9fa; font-weight: bold; }
        tr:hover { background-color: #f5f5f5; }
        .highlight { background-color: yellow; font-weight: bold; }
        .json-field { max-width: 200px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
    </style>
</head>
<body>
    <div class="container">
        <div class="nav">
            <a href="/table/{{ table_name }}" class="btn btn-secondary">← 返回表</a>
        </div>
        
        <h1>🔍 搜索结果</h1>
        
        <div class="search-info">
            <strong>搜索条件:</strong> 在字段 "{{ column }}" 中搜索 "{{ keyword }}"<br>
            <strong>结果数量:</strong> {{ results|length }} 条记录
        </div>
        
        {% if results %}
        <div class="table-wrapper">
        <table>
            <thead>
                <tr>
                    {% for col in structure %}
                    <th>{{ col.name }}</th>
                    {% endfor %}
                    <th>操作</th>
                </tr>
            </thead>
            <tbody>
                {% for record in results %}
                <tr>
                    {% for col in structure %}
                    <td>
                        {% if col.name == column and record[col.name] %}
                            {{ record[col.name]|string|replace(keyword, '<span class="highlight">' + keyword + '</span>')|safe }}
                        {% elif col.name in ['execution_steps', 'similarity_keywords'] and record[col.name] %}
                            <div class="json-field" title="{{ record[col.name]|string }}">{{ record[col.name]|string|truncate(50) }}</div>
                        {% elif col.name == 'result' and record[col.name] and record[col.name]|string|length > 100 %}
                            <div title="{{ record[col.name] }}">{{ record[col.name]|string|truncate(100) }}</div>
                        {% else %}
                            {{ record[col.name] }}
                        {% endif %}
                    </td>
                    {% endfor %}
                    <td>
                        <a href="/record/{{ table_name }}/{{ record.id }}" class="btn">查看/编辑</a>
                    </td>
                </tr>
                {% endfor %}
            </tbody>
        </table>
        </div>
        {% else %}
        <p>未找到匹配的记录。</p>
        {% endif %}
    </div>
</body>
</html>
'''

if __name__ == '__main__':
    print("\n🌐 启动Web数据库编辑器...")
    print("访问地址: http://localhost:5000")
    print("按 Ctrl+C 停止服务器")
    
    app.run(host='0.0.0.0', port=5000, debug=True)