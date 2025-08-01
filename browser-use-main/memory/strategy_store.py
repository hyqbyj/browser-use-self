import json
import os
from typing import Dict, List, Optional
from datetime import datetime
from .memory_manager import ExecutionRecord

class StrategyStore:
    """执行策略存储和检索系统"""
    
    def __init__(self, memory_manager):
        self.memory_manager = memory_manager
    
    async def get_strategy_suggestions(self, question: str) -> Dict:
        """根据历史记录获取策略建议（增强权重计算）"""
        similar_records = await self.memory_manager.find_similar_executions(question, limit=5)
        
        if not similar_records:
            return {
                "has_suggestions": False,
                "message": "未找到相似的历史执行记录",
                "suggested_steps": [],
                "confidence": 0.0
            }
        
        # 分析相似记录，生成建议策略（增强权重计算）
        weighted_steps = []  # 存储带权重的步骤
        confidence_scores = []
        high_quality_records = []
        
        for record in similar_records:
            if record.rating >= 4 and record.success:
                high_quality_records.append(record)
                
                # 计算记录权重：评分越高权重越大
                record_weight = 1.0
                if record.rating == 5:
                    record_weight = 3.0  # 5星记录权重最高
                elif record.rating == 4:
                    record_weight = 1.5  # 4星记录中等权重
                
                # 如果有权重分数，进一步调整
                if hasattr(record, 'weighted_score') and record.weighted_score > 0:
                    record_weight *= (1 + record.weighted_score / 10.0)
                
                # 为每个步骤添加权重
                for step in record.execution_steps:
                    weighted_steps.append({
                        'step': step,
                        'weight': record_weight,
                        'rating': record.rating,
                        'record_id': record.id
                    })
                
                # 计算置信度：高评分记录贡献更多置信度
                base_confidence = (record.rating / 5.0) * 0.8 + 0.2
                weighted_confidence = base_confidence * record_weight
                confidence_scores.append(weighted_confidence)
        
        if not weighted_steps:
            return {
                "has_suggestions": False,
                "message": "找到相似记录但执行质量不足",
                "suggested_steps": [],
                "confidence": 0.0
            }
        
        # 按权重排序步骤，优先选择高权重步骤
        weighted_steps.sort(key=lambda x: x['weight'], reverse=True)
        
        # 去重并保持高权重步骤的优先级
        seen_steps = set()
        unique_steps = []
        for item in weighted_steps:
            step = item['step']
            if step not in seen_steps:
                seen_steps.add(step)
                unique_steps.append(step)
                if len(unique_steps) >= 15:  # 限制步骤数量
                    break
        
        # 计算加权平均置信度
        if confidence_scores:
            avg_confidence = sum(confidence_scores) / len(confidence_scores)
            # 如果有5星记录，额外提升置信度
            five_star_count = sum(1 for r in high_quality_records if r.rating == 5)
            if five_star_count > 0:
                avg_confidence = min(avg_confidence * (1 + five_star_count * 0.1), 1.0)
        else:
            avg_confidence = 0.0
        
        return {
            "has_suggestions": True,
            "message": f"基于{len(high_quality_records)}条高质量记录生成执行建议（含{sum(1 for r in high_quality_records if r.rating == 5)}条五星记录）",
            "suggested_steps": unique_steps,
            "confidence": avg_confidence,
            "similar_records": [
                {
                    "question": record.question,
                    "rating": record.rating,
                    "timestamp": record.timestamp,
                    "task_type": record.task_type,
                    "weighted_score": getattr(record, 'weighted_score', 0)
                } for record in high_quality_records
            ]
        }
    
    def format_strategy_for_display(self, strategy_data: Dict) -> str:
        """格式化策略数据用于前端显示"""
        if not strategy_data["has_suggestions"]:
            return "暂无相关历史策略，将使用智能分析生成执行步骤。"
        
        steps_text = "\n".join([
            f"{i+1}. {step}" for i, step in enumerate(strategy_data["suggested_steps"])
        ])
        
        confidence_text = f"策略置信度：{strategy_data['confidence']:.1%}"
        
        similar_info = "\n\n历史参考记录：\n" + "\n".join([
            f"• {record['question']} （评分：{record['rating']}星）"
            for record in strategy_data["similar_records"]
        ])
        
        return f"""{strategy_data['message']}

建议执行步骤：
{steps_text}

{confidence_text}{similar_info}"""
    
    async def optimize_strategy_with_memory(self, original_strategy: Dict, question: str) -> Dict:
        """结合记忆优化执行策略"""
        memory_suggestions = await self.get_strategy_suggestions(question)
        
        if not memory_suggestions["has_suggestions"]:
            # 没有历史记录，返回原策略
            return {
                **original_strategy,
                "memory_enhanced": False,
                "memory_info": "无相关历史记录"
            }
        
        # 有历史记录，尝试优化策略
        if memory_suggestions["confidence"] > 0.7:
            # 高置信度，使用历史策略
            enhanced_prompt = f"""{original_strategy['task_prompt']}

**🧠 记忆增强提示（基于历史成功经验）：**
根据{len(memory_suggestions['similar_records'])}条相似的成功执行记录，建议采用以下优化策略：

{chr(10).join([f"{i+1}. {step}" for i, step in enumerate(memory_suggestions['suggested_steps'])])}

**策略置信度：{memory_suggestions['confidence']:.1%}**

请结合以上历史经验和当前任务需求，制定最优执行方案。
"""
            
            return {
                "task_prompt": enhanced_prompt,
                "max_steps": min(original_strategy["max_steps"] + 2, 25),  # 略微增加步骤数
                "task_type": original_strategy["task_type"],
                "memory_enhanced": True,
                "memory_info": f"基于{len(memory_suggestions['similar_records'])}条历史记录优化",
                "confidence": memory_suggestions["confidence"]
            }
        else:
            # 低置信度，仅作为参考
            enhanced_prompt = f"""{original_strategy['task_prompt']}

**📚 历史参考（仅供参考）：**
找到一些相关的历史执行记录，但策略置信度较低（{memory_suggestions['confidence']:.1%}）。
可参考的执行思路：
{chr(10).join([f"• {step}" for step in memory_suggestions['suggested_steps'][:99]])}

请主要依据当前任务需求制定执行方案，适当参考上述历史经验。
"""
            
            return {
                **original_strategy,
                "task_prompt": enhanced_prompt,
                "memory_enhanced": True,
                "memory_info": f"参考{len(memory_suggestions['similar_records'])}条历史记录（低置信度）",
                "confidence": memory_suggestions["confidence"]
            }
    
    def get_strategy_templates(self) -> List[Dict]:
        """获取策略模板（基于高评分记录）"""
        records = self.memory_manager.get_all_records(limit=100)
        
        # 筛选高评分记录
        high_quality_records = [
            record for record in records 
            if record.rating >= 4 and record.success
        ]
        
        # 按任务类型分组
        templates = {}
        for record in high_quality_records:
            task_type = record.task_type
            if task_type not in templates:
                templates[task_type] = []
            
            templates[task_type].append({
                "question": record.question,
                "steps": record.execution_steps,
                "rating": record.rating,
                "timestamp": record.timestamp
            })
        
        # 转换为列表格式
        template_list = []
        for task_type, records in templates.items():
            # 按评分排序，取最好的几个
            sorted_records = sorted(records, key=lambda x: x["rating"], reverse=True)[:99]
            template_list.append({
                "task_type": task_type,
                "count": len(records),
                "best_examples": sorted_records
            })
        
        return template_list