#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
快速数据库查看器
用于快速查看 memory.db 数据库内容
"""

import sqlite3
import json
from datetime import datetime
import os

def quick_view_database(db_path="d:\\browser-use-self\\memory_data\\memory.db"):
    """快速查看数据库内容"""
    
    if not os.path.exists(db_path):
        print(f"❌ 数据库文件不存在: {db_path}")
        return
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            print("\n🗄️  Memory数据库快速查看")
            print("=" * 60)
            
            # 1. 显示表信息
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = cursor.fetchall()
            print(f"\n📊 数据库包含 {len(tables)} 个表:")
            for table_name, in tables:
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"  • {table_name}: {count} 条记录")
            
            # 2. 显示最近的执行记录
            print("\n📝 最近5条执行记录:")
            print("-" * 60)
            
            cursor.execute("""
                SELECT id, question, rating, timestamp, task_type, success, execution_time
                FROM execution_records 
                ORDER BY timestamp DESC 
                LIMIT 5
            """)
            
            records = cursor.fetchall()
            if not records:
                print("  暂无执行记录")
            else:
                for i, (record_id, question, rating, timestamp, task_type, success, exec_time) in enumerate(records, 1):
                    status = "✅" if success else "❌"
                    # 格式化时间戳
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        time_str = timestamp[:16]
                    
                    print(f"\n{i}. {status} [{record_id}] 评分: {rating}/5 | 类型: {task_type} | 耗时: {exec_time:.1f}s")
                    print(f"   时间: {time_str}")
                    print(f"   问题: {question[:80]}{'...' if len(question) > 80 else ''}")
            
            # 3. 统计信息
            print("\n📈 统计信息:")
            print("-" * 30)
            
            # 成功率统计
            cursor.execute("SELECT COUNT(*) FROM execution_records WHERE success = 1")
            success_count = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM execution_records")
            total_count = cursor.fetchone()[0]
            
            if total_count > 0:
                success_rate = (success_count / total_count) * 100
                print(f"  成功率: {success_rate:.1f}% ({success_count}/{total_count})")
            
            # 平均评分
            cursor.execute("SELECT AVG(rating) FROM execution_records")
            avg_rating = cursor.fetchone()[0]
            if avg_rating:
                print(f"  平均评分: {avg_rating:.1f}/5")
            
            # 任务类型分布
            cursor.execute("SELECT task_type, COUNT(*) FROM execution_records GROUP BY task_type")
            task_types = cursor.fetchall()
            if task_types:
                print("  任务类型分布:")
                for task_type, count in task_types:
                    print(f"    • {task_type}: {count} 条")
            
            # 4. 相似性索引统计
            cursor.execute("SELECT COUNT(*) FROM similarity_index")
            index_count = cursor.fetchone()[0]
            print(f"  相似性索引: {index_count} 条")
            
            # 5. 最高评分记录
            cursor.execute("""
                SELECT question, rating, timestamp 
                FROM execution_records 
                WHERE rating = (SELECT MAX(rating) FROM execution_records)
                ORDER BY timestamp DESC 
                LIMIT 3
            """)
            
            top_records = cursor.fetchall()
            if top_records:
                max_rating = top_records[0][1]
                print(f"\n🏆 最高评分记录 (评分: {max_rating}):")
                print("-" * 40)
                for i, (question, rating, timestamp) in enumerate(top_records, 1):
                    try:
                        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                        time_str = dt.strftime("%Y-%m-%d %H:%M")
                    except:
                        time_str = timestamp[:16]
                    print(f"  {i}. [{time_str}] {question[:60]}{'...' if len(question) > 60 else ''}")
            
            print("\n" + "=" * 60)
            print("💡 提示: 使用 'python db_editor.py' 进行详细编辑操作")
            
    except Exception as e:
        print(f"❌ 查看数据库时出错: {e}")

def show_record_details(record_id: str, db_path="d:\\browser-use-self\\memory_data\\memory.db"):
    """显示特定记录的详细信息"""
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT id, question, execution_steps, result, rating, timestamp, 
                       task_type, success, execution_time, similarity_keywords
                FROM execution_records 
                WHERE id = ?
            """, (record_id,))
            
            record = cursor.fetchone()
            if not record:
                print(f"❌ 未找到ID为 '{record_id}' 的记录")
                return
            
            (record_id, question, steps_json, result, rating, timestamp, 
             task_type, success, exec_time, keywords_json) = record
            
            print(f"\n📋 记录详情 [{record_id}]")
            print("=" * 50)
            
            status = "✅ 成功" if success else "❌ 失败"
            print(f"状态: {status}")
            print(f"评分: {rating}/5")
            print(f"类型: {task_type}")
            print(f"执行时间: {exec_time:.1f}秒")
            print(f"时间戳: {timestamp}")
            
            print(f"\n问题:\n{question}")
            
            # 解析执行步骤
            try:
                steps = json.loads(steps_json)
                print(f"\n执行步骤:")
                for i, step in enumerate(steps, 1):
                    print(f"  {i}. {step}")
            except:
                print(f"\n执行步骤: {steps_json}")
            
            print(f"\n结果:\n{result}")
            
            # 解析关键词
            try:
                keywords = json.loads(keywords_json)
                if keywords:
                    print(f"\n关键词: {', '.join(keywords)}")
            except:
                if keywords_json:
                    print(f"\n关键词: {keywords_json}")
            
    except Exception as e:
        print(f"❌ 查看记录详情时出错: {e}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        # 如果提供了参数，显示特定记录的详情
        record_id = sys.argv[1]
        show_record_details(record_id)
    else:
        # 否则显示数据库概览
        quick_view_database()