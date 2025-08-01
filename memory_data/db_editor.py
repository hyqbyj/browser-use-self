#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQLite数据库编辑器
用于编辑 memory.db 数据库
"""

import sqlite3
import json
import os
from datetime import datetime
from typing import List, Dict, Any

class DatabaseEditor:
    def __init__(self, db_path="d:\\browser-use-self\\memory_data\\memory.db"):
        self.db_path = db_path
        
    def connect(self):
        """连接数据库"""
        if not os.path.exists(self.db_path):
            raise FileNotFoundError(f"数据库文件不存在: {self.db_path}")
        return sqlite3.connect(self.db_path)
    
    def show_tables(self):
        """显示所有表"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            
            print("\n📊 数据库表:")
            for i, (table_name,) in enumerate(tables, 1):
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  {i}. {table_name} ({count} 条记录)")
            return [table[0] for table in tables]
    
    def show_table_structure(self, table_name: str):
        """显示表结构"""
        with self.connect() as conn:
            cursor = conn.cursor()
            cursor.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()
            
            print(f"\n🏗️  表 '{table_name}' 结构:")
            print("-" * 50)
            for col in columns:
                cid, name, col_type, notnull, default, pk = col
                pk_str = " (主键)" if pk else ""
                null_str = " NOT NULL" if notnull else ""
                default_str = f" DEFAULT {default}" if default else ""
                print(f"  {name}: {col_type}{null_str}{default_str}{pk_str}")
    
    def list_records(self, table_name: str, limit: int = 10, offset: int = 0):
        """列出记录"""
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
            
            print(f"\n📋 表 '{table_name}' 记录 (第 {offset+1}-{min(offset+limit, total)} 条，共 {total} 条):")
            print("=" * 80)
            
            if not records:
                print("  暂无记录")
                return
            
            for i, record in enumerate(records, offset + 1):
                print(f"\n记录 {i}:")
                for col_name, value in zip(columns, record):
                    # 格式化显示
                    if col_name in ['execution_steps', 'similarity_keywords'] and value:
                        try:
                            formatted_value = json.dumps(json.loads(value), ensure_ascii=False, indent=2)
                            print(f"  {col_name}: {formatted_value}")
                        except:
                            print(f"  {col_name}: {value}")
                    elif col_name == 'result' and value and len(str(value)) > 100:
                        print(f"  {col_name}: {str(value)[:100]}...")
                    elif col_name == 'question' and value and len(str(value)) > 80:
                        print(f"  {col_name}: {str(value)[:80]}...")
                    else:
                        print(f"  {col_name}: {value}")
    
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
                print(f"❌ 未找到ID为 '{record_id}' 的记录")
                return None
            
            print(f"\n📋 记录详情 [{record_id}]:")
            print("=" * 60)
            
            record_dict = {}
            for col_name, value in zip(columns, record):
                record_dict[col_name] = value
                
                # 格式化显示
                if col_name in ['execution_steps', 'similarity_keywords'] and value:
                    try:
                        formatted_value = json.dumps(json.loads(value), ensure_ascii=False, indent=2)
                        print(f"{col_name}:\n{formatted_value}\n")
                    except:
                        print(f"{col_name}: {value}\n")
                else:
                    print(f"{col_name}: {value}\n")
            
            return record_dict
    
    def update_record(self, table_name: str, record_id: str, updates: Dict[str, Any]):
        """更新记录"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            # 构建更新语句
            set_clause = ", ".join([f"{col} = ?" for col in updates.keys()])
            values = list(updates.values()) + [record_id]
            
            query = f"UPDATE {table_name} SET {set_clause} WHERE id = ?"
            
            try:
                cursor.execute(query, values)
                conn.commit()
                
                if cursor.rowcount > 0:
                    print(f"✅ 成功更新记录 {record_id}")
                    return True
                else:
                    print(f"❌ 未找到ID为 '{record_id}' 的记录")
                    return False
            except Exception as e:
                print(f"❌ 更新失败: {e}")
                return False
    
    def delete_record(self, table_name: str, record_id: str):
        """删除记录"""
        with self.connect() as conn:
            cursor = conn.cursor()
            
            try:
                cursor.execute(f"DELETE FROM {table_name} WHERE id = ?", (record_id,))
                conn.commit()
                
                if cursor.rowcount > 0:
                    print(f"✅ 成功删除记录 {record_id}")
                    return True
                else:
                    print(f"❌ 未找到ID为 '{record_id}' 的记录")
                    return False
            except Exception as e:
                print(f"❌ 删除失败: {e}")
                return False
    
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
            
            print(f"\n🔍 搜索结果 (在 {column} 中搜索 '{keyword}'):")
            print("=" * 60)
            
            if not records:
                print("  未找到匹配的记录")
                return
            
            for i, record in enumerate(records, 1):
                record_id = record[0]  # 假设第一列是ID
                print(f"\n{i}. 记录ID: {record_id}")
                for col_name, value in zip(columns, record):
                    if col_name == column and value:
                        # 高亮显示匹配的内容
                        highlighted = str(value).replace(keyword, f"**{keyword}**")
                        print(f"  {col_name}: {highlighted}")
                    elif col_name in ['question', 'result'] and value:
                        # 简化显示长文本
                        short_value = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
                        print(f"  {col_name}: {short_value}")

def main():
    """主函数 - 交互式编辑器"""
    editor = DatabaseEditor()
    
    print("\n🗄️  SQLite数据库编辑器")
    print("=" * 50)
    print("数据库路径:", editor.db_path)
    
    try:
        while True:
            print("\n📋 操作菜单:")
            print("1. 显示所有表")
            print("2. 查看表结构")
            print("3. 列出记录")
            print("4. 查看特定记录")
            print("5. 更新记录")
            print("6. 删除记录")
            print("7. 搜索记录")
            print("8. 执行自定义SQL")
            print("0. 退出")
            
            choice = input("\n请选择操作 (0-8): ").strip()
            
            if choice == "0":
                print("👋 再见!")
                break
            elif choice == "1":
                tables = editor.show_tables()
            elif choice == "2":
                table_name = input("请输入表名: ").strip()
                editor.show_table_structure(table_name)
            elif choice == "3":
                table_name = input("请输入表名: ").strip()
                limit = int(input("显示条数 (默认10): ") or "10")
                offset = int(input("跳过条数 (默认0): ") or "0")
                editor.list_records(table_name, limit, offset)
            elif choice == "4":
                table_name = input("请输入表名: ").strip()
                record_id = input("请输入记录ID: ").strip()
                editor.get_record_by_id(table_name, record_id)
            elif choice == "5":
                table_name = input("请输入表名: ").strip()
                record_id = input("请输入记录ID: ").strip()
                
                # 先显示当前记录
                current = editor.get_record_by_id(table_name, record_id)
                if current:
                    print("\n请输入要更新的字段 (格式: 字段名=新值，多个字段用逗号分隔):")
                    print("例如: rating=4,task_type=complex")
                    update_str = input("更新内容: ").strip()
                    
                    if update_str:
                        updates = {}
                        for item in update_str.split(","):
                            if "=" in item:
                                key, value = item.split("=", 1)
                                updates[key.strip()] = value.strip()
                        
                        if updates:
                            editor.update_record(table_name, record_id, updates)
            elif choice == "6":
                table_name = input("请输入表名: ").strip()
                record_id = input("请输入要删除的记录ID: ").strip()
                
                confirm = input(f"确认删除记录 {record_id}? (y/N): ").strip().lower()
                if confirm == "y":
                    editor.delete_record(table_name, record_id)
            elif choice == "7":
                table_name = input("请输入表名: ").strip()
                column = input("请输入搜索的列名: ").strip()
                keyword = input("请输入搜索关键词: ").strip()
                editor.search_records(table_name, column, keyword)
            elif choice == "8":
                sql = input("请输入SQL语句: ").strip()
                if sql:
                    try:
                        with editor.connect() as conn:
                            cursor = conn.cursor()
                            cursor.execute(sql)
                            
                            if sql.upper().startswith("SELECT"):
                                results = cursor.fetchall()
                                print(f"\n查询结果 ({len(results)} 条):")
                                for i, row in enumerate(results, 1):
                                    print(f"  {i}. {row}")
                            else:
                                conn.commit()
                                print(f"✅ SQL执行成功，影响 {cursor.rowcount} 行")
                    except Exception as e:
                        print(f"❌ SQL执行失败: {e}")
            else:
                print("❌ 无效选择，请重试")
                
    except KeyboardInterrupt:
        print("\n\n👋 用户中断，再见!")
    except Exception as e:
        print(f"\n❌ 程序出错: {e}")

if __name__ == "__main__":
    main()