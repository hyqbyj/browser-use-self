import json
import os
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict
import asyncio
from browser_use.llm.messages import UserMessage

@dataclass
class ExecutionRecord:
    """执行记录数据结构"""
    id: str
    question: str
    execution_steps: List[str]
    result: str
    rating: int
    timestamp: str
    task_type: str
    success: bool
    execution_time: float
    similarity_keywords: List[str]

class MemoryManager:
    """长期记忆管理器 - 参考Mem0和MemoryOS的设计理念"""
    
    def __init__(self, data_dir: str = "./memory_data", llm=None):
        self.data_dir = data_dir
        self.llm = llm
        self.db_path = os.path.join(data_dir, "memory.db")
        
        # 确保数据目录存在
        os.makedirs(data_dir, exist_ok=True)
        
        # 初始化数据库
        self._init_database()
    
    def _init_database(self):
        """初始化SQLite数据库"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL;')  # 启用WAL模式，减少锁定
        conn.execute('PRAGMA synchronous=NORMAL;')  # 优化同步模式
        conn.execute('PRAGMA cache_size=10000;')  # 增加缓存大小
        conn.execute('PRAGMA temp_store=memory;')  # 临时存储在内存中
        conn.execute('PRAGMA busy_timeout=30000;')  # 设置忙等待超时30秒
        conn.execute('PRAGMA locking_mode=NORMAL;')  # 设置正常锁定模式，允许外部访问
        cursor = conn.cursor()
        
        # 创建执行记录表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS execution_records (
                id TEXT PRIMARY KEY,
                question TEXT NOT NULL,
                execution_steps TEXT NOT NULL,
                result TEXT NOT NULL,
                rating INTEGER NOT NULL,
                timestamp TEXT NOT NULL,
                task_type TEXT NOT NULL,
                success BOOLEAN NOT NULL,
                execution_time REAL NOT NULL,
                similarity_keywords TEXT NOT NULL
            )
        ''')
        
        # 创建相似性索引表
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS similarity_index (
                keyword TEXT NOT NULL,
                record_id TEXT NOT NULL,
                weight REAL NOT NULL,
                FOREIGN KEY (record_id) REFERENCES execution_records (id)
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def _generate_record_id(self, question: str, timestamp: str) -> str:
        """生成记录ID"""
        content = f"{question}_{timestamp}"
        return hashlib.md5(content.encode()).hexdigest()[:12]
    
    async def _extract_keywords(self, question: str, steps: List[str]) -> List[str]:
        """使用LLM提取关键词用于相似性匹配"""
        if not self.llm:
            # 简单的关键词提取
            import re
            text = f"{question} {' '.join(steps)}"
            keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
            return list(set([kw.lower() for kw in keywords if len(kw) > 1]))[:10]
        
        try:
            prompt = f"""
请从以下问题和执行步骤中提取5-10个最重要的关键词，用于后续的相似性匹配。

问题：{question}
执行步骤：{' '.join(steps)}

请只返回关键词，用逗号分隔，不要有其他内容：
"""
            
            messages = [UserMessage(content=prompt)]
            response = await self.llm.ainvoke(messages)
            
            if hasattr(response, 'content'):
                keywords_text = response.content
            elif hasattr(response, 'text'):
                keywords_text = response.text
            else:
                keywords_text = str(response)
            
            keywords = [kw.strip().lower() for kw in keywords_text.split(',') if kw.strip()]
            return keywords[:10]
            
        except Exception as e:
            print(f"关键词提取失败：{e}")
            # 回退到简单提取
            import re
            text = f"{question} {' '.join(steps)}"
            keywords = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text)
            return list(set([kw.lower() for kw in keywords if len(kw) > 1]))[:10]
    
    async def store_execution(self, question: str, execution_steps: List[str], 
                            result: str, rating: int, task_type: str = "unknown",
                            success: bool = True, execution_time: float = 0.0) -> str:
        """存储执行记录（仅当评分>=4时）"""
        if rating < 4:
            return "评分低于四星，不存储到记忆系统中"
        
        timestamp = datetime.now().isoformat()
        record_id = self._generate_record_id(question, timestamp)
        
        # 提取关键词
        keywords = await self._extract_keywords(question, execution_steps)
        
        # 创建记录
        record = ExecutionRecord(
            id=record_id,
            question=question,
            execution_steps=execution_steps,
            result=result,
            rating=rating,
            timestamp=timestamp,
            task_type=task_type,
            success=success,
            execution_time=execution_time,
            similarity_keywords=keywords
        )
        
        # 存储到数据库
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA busy_timeout=30000;')
        conn.execute('PRAGMA locking_mode=NORMAL;')
        cursor = conn.cursor()
        
        try:
            # 插入主记录
            cursor.execute('''
                INSERT OR REPLACE INTO execution_records 
                (id, question, execution_steps, result, rating, timestamp, 
                 task_type, success, execution_time, similarity_keywords)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                record.id, record.question, json.dumps(record.execution_steps, ensure_ascii=False),
                record.result, record.rating, record.timestamp, record.task_type,
                record.success, record.execution_time, json.dumps(record.similarity_keywords, ensure_ascii=False)
            ))
            
            # 删除旧的相似性索引
            cursor.execute('DELETE FROM similarity_index WHERE record_id = ?', (record_id,))
            
            # 插入相似性索引
            for keyword in keywords:
                cursor.execute('''
                    INSERT INTO similarity_index (keyword, record_id, weight)
                    VALUES (?, ?, ?)
                ''', (keyword, record_id, 1.0))
            
            conn.commit()
            return f"执行记录已成功存储到记忆系统：{record_id}"
            
        except Exception as e:
            conn.rollback()
            return f"记忆存储失败：{str(e)}"
        finally:
            conn.close()
    
    async def find_similar_executions(self, question: str, limit: int = 3) -> List[ExecutionRecord]:
        """查找相似的执行记录（增强权重计算）"""
        # 提取当前问题的关键词
        current_keywords = await self._extract_keywords(question, [])
        
        if not current_keywords:
            return []
        
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA busy_timeout=30000;')
        conn.execute('PRAGMA locking_mode=NORMAL;')
        cursor = conn.cursor()
        
        try:
            # 查找匹配的记录，使用增强的权重计算
            placeholders = ','.join(['?' for _ in current_keywords])
            query = f'''
                SELECT r.*, 
                       COUNT(s.keyword) as match_count,
                       -- 计算综合权重分数：关键词匹配数 * 评分权重 * 成功权重
                       (COUNT(s.keyword) * 1.0 + 
                        r.rating * 2.0 + 
                        CASE WHEN r.success = 1 THEN 1.0 ELSE 0.0 END +
                        CASE WHEN r.rating >= 5 THEN 3.0 
                             WHEN r.rating >= 4 THEN 1.5 
                             ELSE 0.0 END) as weighted_score
                FROM execution_records r
                JOIN similarity_index s ON r.id = s.record_id
                WHERE s.keyword IN ({placeholders})
                GROUP BY r.id
                -- 优先按权重分数排序，然后按评分、时间排序
                ORDER BY weighted_score DESC, r.rating DESC, r.timestamp DESC
                LIMIT ?
            '''
            
            cursor.execute(query, current_keywords + [limit])
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                record = ExecutionRecord(
                    id=row[0],
                    question=row[1],
                    execution_steps=json.loads(row[2]),
                    result=row[3],
                    rating=row[4],
                    timestamp=row[5],
                    task_type=row[6],
                    success=bool(row[7]),
                    execution_time=row[8],
                    similarity_keywords=json.loads(row[9])
                )
                # 添加权重分数信息用于调试
                record.weighted_score = row[11] if len(row) > 11 else 0
                records.append(record)
            
            return records
            
        except Exception as e:
            print(f"查找相似记录失败：{e}")
            return []
        finally:
            conn.close()
    
    def get_all_records(self, limit: int = 50) -> List[ExecutionRecord]:
        """获取所有记录"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA busy_timeout=30000;')
        conn.execute('PRAGMA locking_mode=NORMAL;')
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                SELECT * FROM execution_records 
                ORDER BY timestamp DESC 
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            
            records = []
            for row in rows:
                record = ExecutionRecord(
                    id=row[0],
                    question=row[1],
                    execution_steps=json.loads(row[2]),
                    result=row[3],
                    rating=row[4],
                    timestamp=row[5],
                    task_type=row[6],
                    success=bool(row[7]),
                    execution_time=row[8],
                    similarity_keywords=json.loads(row[9])
                )
                records.append(record)
            
            return records
            
        except Exception as e:
            print(f"获取记录失败：{e}")
            return []
        finally:
            conn.close()
    
    def delete_record(self, record_id: str) -> bool:
        """删除记录"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA busy_timeout=30000;')
        conn.execute('PRAGMA locking_mode=NORMAL;')
        cursor = conn.cursor()
        
        try:
            cursor.execute('DELETE FROM similarity_index WHERE record_id = ?', (record_id,))
            cursor.execute('DELETE FROM execution_records WHERE id = ?', (record_id,))
            conn.commit()
            return True
        except Exception as e:
            print(f"删除记录失败：{e}")
            conn.rollback()
            return False
        finally:
            conn.close()
    
    def get_statistics(self) -> Dict:
        """获取记忆统计信息"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.execute('PRAGMA journal_mode=WAL;')
        conn.execute('PRAGMA busy_timeout=30000;')
        conn.execute('PRAGMA locking_mode=NORMAL;')
        cursor = conn.cursor()
        
        try:
            # 总记录数
            cursor.execute('SELECT COUNT(*) FROM execution_records')
            total_records = cursor.fetchone()[0]
            
            # 按评分统计
            cursor.execute('''
                SELECT rating, COUNT(*) 
                FROM execution_records 
                GROUP BY rating 
                ORDER BY rating DESC
            ''')
            rating_stats = dict(cursor.fetchall())
            
            # 按任务类型统计
            cursor.execute('''
                SELECT task_type, COUNT(*) 
                FROM execution_records 
                GROUP BY task_type
            ''')
            type_stats = dict(cursor.fetchall())
            
            # 成功率
            cursor.execute('SELECT AVG(CAST(success AS FLOAT)) FROM execution_records')
            success_rate = cursor.fetchone()[0] or 0.0
            
            return {
                'total_records': total_records,
                'rating_distribution': rating_stats,
                'task_type_distribution': type_stats,
                'success_rate': success_rate
            }
            
        except Exception as e:
            print(f"获取统计信息失败：{e}")
            return {}
        finally:
            conn.close()