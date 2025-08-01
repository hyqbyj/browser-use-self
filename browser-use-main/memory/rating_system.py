from typing import Dict, List, Optional
from datetime import datetime
import json

class RatingSystem:
    """评分和反馈系统"""
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
    
    def create_rating_interface_data(self, result: str, execution_data: Dict) -> Dict:
        """创建评分界面所需的数据"""
        return {
            "result": result,
            "execution_data": execution_data,
            "rating_options": [
                {"value": 5, "label": "⭐⭐⭐⭐⭐ 完美执行", "description": "结果完全符合预期，执行过程高效"},
                {"value": 4, "label": "⭐⭐⭐⭐ 良好执行", "description": "结果基本符合预期，有小幅改进空间"},
                {"value": 3, "label": "⭐⭐⭐ 一般执行", "description": "结果可用但不够理想"},
                {"value": 2, "label": "⭐⭐ 较差执行", "description": "结果部分有用但存在明显问题"},
                {"value": 1, "label": "⭐ 失败执行", "description": "结果基本无用或完全错误"}
            ],
            "storage_threshold": 4,
            "storage_note": "只有4星及以上的执行记录会被保存到记忆模块中，用于优化未来的类似任务。"
        }
    
    async def process_rating(self, rating: int, question: str, execution_steps: List[str], 
                           result: str, task_type: str = "unknown", 
                           execution_time: float = 0.0, feedback: str = "") -> Dict:
        """处理用户评分"""
        if rating < 1 or rating > 5:
            return {
                "success": False,
                "message": "评分必须在1-5星之间",
                "stored": False
            }
        
        # 判断是否成功（4星及以上认为成功）
        success = rating >= 4
        
        # 存储记录（只有4星及以上才存储）
        stored = False
        storage_message = ""
        
        if rating >= 4:
            try:
                storage_result = await self.memory_manager.store_execution(
                    question=question,
                    execution_steps=execution_steps,
                    result=result,
                    rating=rating,
                    task_type=task_type,
                    success=success,
                    execution_time=execution_time
                )
                stored = True
                storage_message = f"✅ {storage_result}"
            except Exception as e:
                storage_message = f"❌ 存储失败：{str(e)}"
        else:
            storage_message = "⚠️ 评分低于4星，未存储到记忆模块"
        
        # 生成反馈消息
        rating_labels = {
            5: "完美执行",
            4: "良好执行", 
            3: "一般执行",
            2: "较差执行",
            1: "失败执行"
        }
        
        # 获取当前记忆库统计
        current_records_count = len(self.memory_manager.get_all_records())
        
        feedback_message = f"""
📊 **任务执行评价结果**

⭐ **本次评分：{rating}星 - {rating_labels[rating]}**

{storage_message}

📋 **评分机制说明**
• 五星（完美执行）：策略将作为优秀模板保存
• 四星（良好执行）：执行记录保存用于优化改进
• 三星（一般执行）：不保存，避免影响系统学习质量
• 二星（较差执行）：不保存，建议重新尝试
• 一星（失败执行）：不保存，需要调整执行策略

🧠 **智能记忆系统状态**
• 记忆库容量：{current_records_count}条优质执行策略
• 学习状态：{'持续优化中' if current_records_count > 0 else '等待首个优质记录'}
• 这些记录将帮助系统在处理类似问题时提供更精准的执行策略
"""
        
        if feedback:
            feedback_message += f"\n📝 **用户反馈意见**\n{feedback}"
        
        return {
            "success": True,
            "message": feedback_message,
            "stored": stored,
            "rating": rating,
            "storage_message": storage_message
        }
    
    def get_rating_statistics(self) -> Dict:
        """获取评分统计信息"""
        stats = self.memory_manager.get_statistics()
        
        if not stats:
            return {
                "total_ratings": 0,
                "average_rating": 0.0,
                "rating_distribution": {},
                "storage_rate": 0.0
            }
        
        rating_dist = stats.get('rating_distribution', {})
        total_ratings = sum(rating_dist.values())
        
        if total_ratings == 0:
            return {
                "total_ratings": 0,
                "average_rating": 0.0,
                "rating_distribution": {},
                "storage_rate": 0.0
            }
        
        # 计算平均评分
        weighted_sum = sum(rating * count for rating, count in rating_dist.items())
        average_rating = weighted_sum / total_ratings
        
        # 计算存储率（4星及以上的比例）
        high_rating_count = sum(count for rating, count in rating_dist.items() if rating >= 4)
        storage_rate = high_rating_count / total_ratings if total_ratings > 0 else 0.0
        
        return {
            "total_ratings": total_ratings,
            "average_rating": average_rating,
            "rating_distribution": rating_dist,
            "storage_rate": storage_rate,
            "success_rate": stats.get('success_rate', 0.0)
        }
    
    def format_rating_stats_for_display(self) -> str:
        """格式化评分统计信息用于显示"""
        stats = self.get_rating_statistics()
        
        if stats['total_ratings'] == 0:
            return "📊 **记忆系统统计报告**\n\n暂无评分数据，开始使用系统后将显示详细统计信息。"
        
        # 生成评分分布的可视化条形图
        rating_bars = ""
        rating_labels = {
            5: "完美执行",
            4: "良好执行", 
            3: "一般执行",
            2: "较差执行",
            1: "失败执行"
        }
        
        for rating in range(5, 0, -1):
            count = stats['rating_distribution'].get(rating, 0)
            percentage = (count / stats['total_ratings']) * 100 if stats['total_ratings'] > 0 else 0
            bar = "█" * int(percentage / 5)  # 每5%一个方块
            label = rating_labels.get(rating, f"{rating}星")
            rating_bars += f"{rating}星 {label}: {count:3d}次 ({percentage:4.1f}%) {bar}\n"
        
        # 计算记忆库质量指标
        high_quality_count = sum(count for rating, count in stats['rating_distribution'].items() if rating >= 4)
        quality_percentage = (high_quality_count / stats['total_ratings']) * 100 if stats['total_ratings'] > 0 else 0
        
        return f"""
📊 **智能记忆系统统计报告**

📈 **总体数据**
• 累计评分次数：{stats['total_ratings']}次
• 平均执行评分：{stats['average_rating']:.1f}星
• 任务成功率：{stats['success_rate']:.1%}
• 记忆库收录率：{stats['storage_rate']:.1%}（四星及以上）

⭐ **评分分布详情**
{rating_bars}
🧠 **记忆库状态**
• 高质量记录：{high_quality_count}条（{quality_percentage:.1f}%）
• 记忆库总容量：{high_quality_count}条优质执行策略
• 学习状态：{'活跃学习中' if high_quality_count > 0 else '等待优质记录'}

💡 **说明**
只有四星及以上的执行记录会被保存到记忆模块中，用于优化未来类似任务的执行策略。
"""
    
    def should_store_execution(self, rating: int) -> bool:
        """判断是否应该存储执行记录"""
        return rating >= 4
    
    def get_quality_feedback(self, rating: int) -> str:
        """根据评分获取质量反馈"""
        feedback_map = {
            5: "🎉 完美！这次执行将成为未来类似任务的优秀模板。",
            4: "👍 很好！这次执行记录已保存，将帮助改进未来的任务执行。",
            3: "😐 还可以，但还有改进空间。此记录不会保存到记忆模块。",
            2: "😕 执行效果不理想，建议重新尝试或调整策略。",
            1: "😞 执行失败，请检查任务描述或尝试不同的方法。"
        }
        return feedback_map.get(rating, "未知评分")