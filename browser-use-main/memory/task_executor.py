import asyncio
import time
import json
import re
from typing import Dict, List, Optional, Tuple
from datetime import datetime
from browser_use import Agent
from browser_use.llm.messages import UserMessage

class TaskExecutor:
    """任务执行器 - 负责任务分析、执行和结果管理"""
    
    def __init__(self, llm, memory_manager, strategy_store, rating_system):
        self.llm = llm
        self.memory_manager = memory_manager
        self.strategy_store = strategy_store
        self.rating_system = rating_system
        self.current_execution = None
        self.execution_timeout = 1200  # 20分钟超时
    
    async def analyze_task(self, question: str) -> Dict:
        """分析任务并生成执行计划"""
        try:
            # 1. 从记忆中查找相似任务
            similar_records = await self.memory_manager.find_similar_executions(question, limit=3)
            
            # 2. 获取策略建议
            strategy_suggestions = await self.strategy_store.get_strategy_suggestions(
                question
            )
            
            # 3. 使用LLM分析任务
            analysis_prompt = self._build_analysis_prompt(question, similar_records, strategy_suggestions)
            
            messages = [UserMessage(content=analysis_prompt)]
            analysis_result = await self.llm.ainvoke(messages)
            
            # 4. 解析分析结果
            analysis_data = self._parse_analysis_result(analysis_result, question)
            
            # 5. 生成执行计划
            execution_plan = {
                "task_id": f"task_{int(time.time())}",
                "question": question,
                "task_type": analysis_data.get("task_type", "simple"),
                "estimated_steps": analysis_data.get("max_steps", 8),
                "execution_strategy": analysis_data.get("execution_strategy", ""),
                "needs_login": analysis_data.get("needs_login", False),
                "similar_records": similar_records,
                "strategy_suggestions": strategy_suggestions,
                "created_at": datetime.now().isoformat(),
                "status": "planned"
            }
            
            return execution_plan
            
        except Exception as e:
            # 返回默认计划
            return {
                "task_id": f"task_{int(time.time())}",
                "question": question,
                "task_type": "simple",
                "estimated_steps": 8,
                "execution_strategy": "使用默认策略执行任务",
                "needs_login": False,
                "similar_records": [],
                "strategy_suggestions": [],
                "created_at": datetime.now().isoformat(),
                "status": "planned",
                "analysis_error": str(e)
            }
    
    def _build_analysis_prompt(self, question: str, similar_records: List, strategy_suggestions: List) -> str:
        """构建任务分析提示"""
        prompt = f"""
你是一个专业的浏览器自动化任务分析专家，需要分析用户的需求并生成详细的具体执行步骤。

用户需求：{question}

"""
        
        if similar_records:
            prompt += "\n🎯 **【重要】历史成功案例参考（请优先参考这些经过验证的成功方案）：**\n"
            for i, record in enumerate(similar_records[:3], 1):
                rating = record.get('rating', 0)
                success_indicator = "⭐" * rating + f" ({rating}/5星)"
                prompt += f"\n**案例{i}** {success_indicator}\n"
                prompt += f"问题：{record.get('question', '')}\n"
                execution_steps = record.get('execution_steps', [])
                if execution_steps:
                    prompt += f"**已验证的成功步骤：**\n"
                    for step in execution_steps[:10]:
                        prompt += f"  ✓ {step}\n"
                prompt += f"执行时间：{record.get('execution_time', 0):.1f}秒\n"
                if record.get('task_type'):
                    prompt += f"任务类型：{record.get('task_type')}\n"
                prompt += "\n"
        
        if strategy_suggestions and strategy_suggestions.get('has_suggestions', False):
            confidence = strategy_suggestions.get('confidence', 0)
            prompt += f"\n💡 **策略建议（置信度：{confidence:.1%}）：**\n"
            suggested_steps = strategy_suggestions.get('suggested_steps', [])
            for suggestion in suggested_steps[:8]:
                prompt += f"• {suggestion}\n"
        
        prompt += f"""

**【核心要求】请基于以上历史成功案例制定执行方案：**

**优先级指导：**
1. **最高优先级**：直接复用上述历史成功案例中评分4星及以上的步骤
2. **高优先级**：参考相似案例的执行思路和关键操作
3. **中等优先级**：结合当前问题特点进行必要的适应性调整
4. **低优先级**：添加新的创新步骤（仅在历史案例不足时）

**执行步骤要求：**
1. 每个步骤必须具体明确，包含具体的操作动作
2. 步骤要符合浏览器自动化的实际操作流程
3. 考虑网页加载、元素识别、点击、输入等具体操作
4. **重点**：优先采用历史成功案例中的有效步骤
5. 针对问题"{question}"进行个性化定制

**如果有历史成功案例，请在制定步骤时：**
- 保留历史案例中的核心成功步骤
- 调整具体的关键词、网站、操作对象以适应当前问题
- 保持历史案例中证明有效的操作顺序和逻辑

请以JSON格式返回：
{{
  "task_type": "simple或complex",
  "max_steps": 数字,
  "needs_login": true或false,
  "execution_strategy": "详细的具体执行步骤，每行一个步骤，格式如：1. 具体操作描述\\n2. 具体操作描述\\n...",
  "success_factors": ["成功要点1", "成功要点2"]
}}

只返回JSON格式，不要其他文字。execution_strategy字段必须包含具体的分步操作，不能是概括性描述。
"""
        
        return prompt
    
    def _parse_analysis_result(self, analysis_result, question: str = "") -> Dict:
        """解析LLM分析结果"""
        try:
            # 提取文本内容
            analysis_text = None
            if hasattr(analysis_result, 'completion'):
                # 处理ChatInvokeCompletion对象
                analysis_text = analysis_result.completion
            elif hasattr(analysis_result, 'content'):
                analysis_text = analysis_result.content
            elif hasattr(analysis_result, 'text'):
                analysis_text = analysis_result.text
            elif isinstance(analysis_result, str):
                analysis_text = analysis_result
            else:
                analysis_text = str(analysis_result)
            
            if not analysis_text:
                raise Exception("无法获取分析结果")
            
            print(f"提取的分析文本: {analysis_text[:200]}...")  # 调试信息
            
            # 解析JSON - 改进的多重尝试策略
            import re
            import json
            
            # 清理文本
            analysis_text = analysis_text.strip()
            
            # 尝试1: 直接解析（如果整个文本就是JSON）
            try:
                return json.loads(analysis_text)
            except json.JSONDecodeError:
                pass
            
            # 尝试2: 移除markdown代码块标记
            if '```json' in analysis_text or '```' in analysis_text:
                # 提取代码块中的内容
                code_block_match = re.search(r'```(?:json)?\s*([\s\S]*?)```', analysis_text)
                if code_block_match:
                    json_content = code_block_match.group(1).strip()
                    try:
                        return json.loads(json_content)
                    except json.JSONDecodeError:
                        pass
            
            # 尝试3: 使用改进的正则表达式提取JSON（支持嵌套）
            json_patterns = [
                r'\{[\s\S]*\}',  # 最宽泛的匹配
                r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}',  # 支持一层嵌套
                r'\{(?:[^{}]|\{[^{}]*\})*\}'  # 另一种嵌套模式
            ]
            
            for pattern in json_patterns:
                json_match = re.search(pattern, analysis_text, re.DOTALL)
                if json_match:
                    json_string = json_match.group(0)
                    try:
                        # 尝试修复常见的JSON格式问题
                        json_string = self._fix_json_format(json_string)
                        print(f"提取的JSON字符串: {json_string[:200]}...")  # 调试信息
                        return json.loads(json_string)
                    except json.JSONDecodeError as je:
                        print(f"JSON解析错误: {je}")
                        continue
            
            # 尝试4: 手动解析关键字段
            parsed_result = self._manual_parse_fields(analysis_text)
            if parsed_result:
                return parsed_result
            
            raise Exception("所有JSON解析方法都失败")
                
        except Exception as e:
            print(f"解析分析结果失败：{e}")
            print(f"原始结果类型: {type(analysis_result)}")
            print(f"原始结果内容: {str(analysis_result)[:500]}...")  # 调试信息
            # 根据问题生成针对性的默认策略
            default_strategy = self._generate_default_strategy(question)
            return {
                "task_type": "simple",
                "max_steps": 8,
                "needs_login": False,
                "execution_strategy": default_strategy,
                "success_factors": []
            }
    
    def _fix_json_format(self, json_string: str) -> str:
        """修复常见的JSON格式问题"""
        # 移除可能的前后缀
        json_string = json_string.strip()
        
        # 修复单引号为双引号
        json_string = re.sub(r"(?<!\\)'([^']*?)(?<!\\)'", r'"\1"', json_string)
        
        # 修复未引用的键名
        json_string = re.sub(r'(\w+)\s*:', r'"\1":', json_string)
        
        # 修复尾随逗号
        json_string = re.sub(r',\s*([}\]])', r'\1', json_string)
        
        return json_string
    
    def _manual_parse_fields(self, text: str) -> Optional[Dict]:
        """手动解析关键字段"""
        try:
            import re
            
            result = {
                "task_type": "simple",
                "max_steps": 8,
                "needs_login": False,
                "execution_strategy": "",
                "success_factors": []
            }
            
            # 提取task_type
            task_type_match = re.search(r'["\']?task_type["\']?\s*:\s*["\']?(simple|complex)["\']?', text, re.IGNORECASE)
            if task_type_match:
                result["task_type"] = task_type_match.group(1)
            
            # 提取max_steps
            max_steps_match = re.search(r'["\']?max_steps["\']?\s*:\s*(\d+)', text, re.IGNORECASE)
            if max_steps_match:
                result["max_steps"] = int(max_steps_match.group(1))
            
            # 提取needs_login
            needs_login_match = re.search(r'["\']?needs_login["\']?\s*:\s*(true|false)', text, re.IGNORECASE)
            if needs_login_match:
                result["needs_login"] = needs_login_match.group(1).lower() == 'true'
            
            # 提取execution_strategy
            strategy_match = re.search(r'["\']?execution_strategy["\']?\s*:\s*["\']([^"]*)["\']', text, re.DOTALL)
            if strategy_match:
                result["execution_strategy"] = strategy_match.group(1)
            
            # 如果提取到了关键信息，返回结果
            if result["execution_strategy"]:
                return result
            
            return None
            
        except Exception as e:
            print(f"手动解析失败: {e}")
            return None
    
    def _generate_default_strategy(self, question: str) -> str:
        """根据问题生成默认执行策略"""
        if not question:
            return "1. 打开浏览器并访问搜索引擎\n2. 在搜索框中输入相关关键词\n3. 点击搜索按钮执行搜索\n4. 浏览搜索结果页面\n5. 点击相关链接获取详细信息\n6. 提取并整理所需信息\n7. 生成最终答案"
        
        question_lower = question.lower()
        
        # 人工智能/AI相关问题
        if any(keyword in question_lower for keyword in ['人工智能', 'ai', '机器学习', '深度学习', 'gpt', 'llm']):
            return "1. 打开浏览器并访问技术资讯网站（如机器之心、AI科技大本营）\n2. 在搜索框中输入'人工智能发展趋势'关键词\n3. 点击搜索按钮执行搜索\n4. 浏览搜索结果，重点关注权威技术媒体的文章\n5. 点击最新的相关文章链接\n6. 仔细阅读文章内容，提取关键技术趋势信息\n7. 整理并总结5个主要发展趋势，每点控制在50字以内\n8. 生成结构化的答案输出"
        
        # 比较类问题
        elif any(keyword in question_lower for keyword in ['比较', '对比', 'vs', '区别']):
            return "1. 打开浏览器并访问搜索引擎\n2. 搜索第一个对比对象的详细信息\n3. 点击权威网站链接获取准确信息\n4. 记录第一个对象的关键特征和参数\n5. 返回搜索页面，搜索第二个对比对象\n6. 点击相关链接获取第二个对象的信息\n7. 对比两者的功能、价格、性能等方面\n8. 生成详细的对比分析报告"
        
        # 购物/电商相关
        elif any(keyword in question_lower for keyword in ['京东', '淘宝', '购买', '价格', '商品']):
            return "1. 打开浏览器并访问指定电商平台\n2. 在搜索框中输入商品关键词\n3. 点击搜索按钮执行商品搜索\n4. 浏览搜索结果页面，筛选相关商品\n5. 点击目标商品链接进入详情页\n6. 查看商品价格、规格、评价等信息\n7. 记录关键商品信息和用户评价\n8. 整理并生成商品分析报告"
        
        # GitHub/开源项目相关
        elif any(keyword in question_lower for keyword in ['github', '开源', '项目', '代码']):
            return "1. 打开浏览器并访问GitHub官网\n2. 在搜索框中输入相关技术关键词\n3. 设置搜索过滤条件（如语言、星标数等）\n4. 浏览搜索结果，按热门程度排序\n5. 点击前3个热门项目链接\n6. 查看项目的README、星标数、贡献者等信息\n7. 分析项目的功能特点和技术栈\n8. 生成项目对比分析报告"
        
        # 知乎/社区讨论相关
        elif any(keyword in question_lower for keyword in ['知乎', '讨论', '观点', '社区']):
            return "1. 打开浏览器并访问知乎网站\n2. 在搜索框中输入讨论话题关键词\n3. 点击搜索按钮执行搜索\n4. 浏览搜索结果，筛选高质量问答\n5. 点击热门问题链接进入详情页\n6. 阅读高赞回答和评论内容\n7. 提取主要观点和论据\n8. 整理并总结讨论的核心观点"
        
        # 默认通用策略
        else:
            return f"1. 打开浏览器并访问搜索引擎\n2. 在搜索框中输入'{question}'相关关键词\n3. 点击搜索按钮执行搜索\n4. 浏览搜索结果页面，筛选权威来源\n5. 点击最相关的搜索结果链接\n6. 仔细阅读页面内容，提取关键信息\n7. 如需更多信息，继续访问其他相关链接\n8. 整理并生成完整的答案"
    
    async def execute_task(self, execution_plan: Dict, browser_session) -> Dict:
        """执行任务"""
        task_id = execution_plan["task_id"]
        question = execution_plan["question"]
        
        # 更新执行状态
        execution_plan["status"] = "executing"
        execution_plan["start_time"] = time.time()

        execution_plan["replanned"] = False
        self.current_execution = execution_plan
        
        agent = None
        
        try:
            # 构建任务提示
            task_prompt = self._build_task_prompt(execution_plan)
            
            # 创建Agent（优化参数）
            agent = Agent(
                task=task_prompt,
                llm=self.llm,
                use_vision=True,
                browser_session=browser_session,
                max_steps=min(execution_plan["estimated_steps"], 99),  # 限制最大步骤数
                action_description_strategy="concise",  # 使用简洁模式
                retry_attempts=2,
                wait_between_actions=2.0  # 减少等待时间
            )
            
            # 执行任务（带超时控制）
            result = await asyncio.wait_for(
                agent.run(), 
                timeout=self.execution_timeout
            )
            
            # 提取结果
            extracted_result = await self._extract_result_content(
                agent.state.history, result, question
            )
            
            # 更新执行状态
            execution_plan["status"] = "completed"
            execution_plan["end_time"] = time.time()
            execution_plan["execution_time"] = execution_plan["end_time"] - execution_plan["start_time"]
            execution_plan["result"] = extracted_result
            execution_plan["agent_history"] = agent.state.history
            
            return execution_plan
                        
        except asyncio.TimeoutError:
            # 超时处理 - 尝试提取已收集的信息
            partial_result = "⏰ 任务执行超时，但已收集到以下信息：\n\n"
            if agent and hasattr(agent, 'state') and agent.state.history:
                try:
                    # 从历史记录中提取部分结果
                    partial_content = await self._extract_result_content(
                        agent.state.history, None, question
                    )
                    if partial_content and partial_content != "未能提取到有效结果内容":
                        partial_result += partial_content
                    else:
                        partial_result += "未能从执行历史中提取到有效信息。"
                except Exception as e:
                    partial_result += f"提取部分结果时出错：{str(e)}"
            else:
                partial_result += "执行超时且无法获取部分结果。"
            
            execution_plan["status"] = "timeout"
            execution_plan["end_time"] = time.time()
            execution_plan["execution_time"] = self.execution_timeout
            execution_plan["result"] = partial_result
            return execution_plan
                
        except Exception as e:
            execution_plan["status"] = "failed"
            execution_plan["end_time"] = time.time()
            execution_plan["execution_time"] = time.time() - execution_plan["start_time"]
            execution_plan["result"] = f"执行失败：{str(e)}"
            execution_plan["error"] = str(e)
            return execution_plan
    
    def _build_task_prompt(self, execution_plan: Dict) -> str:
        """构建任务执行提示"""
        question = execution_plan["question"]
        task_type = execution_plan["task_type"]
        strategy = execution_plan["execution_strategy"]
        similar_records = execution_plan.get("similar_records", [])
        
        # 基础提示
        if task_type == "complex":
            prompt = f"""
**角色：** 你是一个高效的网站操作助手，能够快速执行网站操作任务。

**用户需求：** {question}

**执行策略：**
{strategy}
"""
        else:
            search_url = f"https://www.bing.com/search?q={question.replace(' ', '+')}"
            prompt = f"""
**角色：** 你是一个高效的信息搜索专家，专门快速获取准确信息。

**用户需求：** {question}

**执行策略：**
{strategy if strategy else f'1. 访问搜索网址：{search_url}\n2. 快速分析搜索结果\n3. 点击最相关链接\n4. 提取核心信息'}
"""
        
        # 添加历史经验
        if similar_records:
            prompt += "\n\n**📚 历史成功经验参考：**\n"
            for i, record in enumerate(similar_records[:99], 1):  # 减少到1个
                steps = record.get('execution_steps', [])
                if steps:
                    prompt += f"{i}. 成功步骤：{steps[:99]}\n"  # 减少步骤数
        
        # 添加执行要求
        prompt += """

**重要执行要求：**
1. 直接执行搜索，快速定位目标
2. 优先点击权威、官方链接
3. 快速提取核心信息
4. 遇到错误立即换方法
5. 最终输出清晰总结

现在开始执行任务：
"""
        
        return prompt
    
    async def _extract_result_content(self, history, result, original_question: str) -> str:
        """提取执行结果内容并进行AI智能梳理"""
        try:
            # 从final_result提取
            final_result = history.final_result()
            if final_result and isinstance(final_result, str):
                chinese_content = self._extract_chinese_lines(final_result)
                if chinese_content:
                    # 使用AI梳理和规范化内容
                    processed_content = await self._ai_process_content(chinese_content, original_question)
                    return processed_content
            
            # 从最后一步结果提取
            if history.history and len(history.history) > 0:
                last_step = history.history[-1]
                if hasattr(last_step, 'result') and last_step.result:
                    for action_result in last_step.result:
                        if hasattr(action_result, 'extracted_content') and action_result.extracted_content:
                            chinese_content = self._extract_chinese_lines(action_result.extracted_content)
                            if chinese_content:
                                # 使用AI梳理和规范化内容
                                processed_content = await self._ai_process_content(chinese_content, original_question)
                                return processed_content
            
            # 从完整结果日志提取
            result_str = str(result)
            chinese_content = self._extract_chinese_from_log(result_str)
            if chinese_content:
                # 使用AI梳理和规范化内容
                processed_content = await self._ai_process_content(chinese_content, original_question)
                return processed_content
            
            return "未能提取到有效结果内容"
            
        except Exception as e:
            return f"提取结果时出错：{str(e)}"
    
    def _extract_chinese_lines(self, text: str) -> str:
        """从文本中提取中文行"""
        if not text:
            return None
        
        lines = text.split('\n')
        chinese_lines = []
        
        for line in lines:
            line = line.strip()
            if (line and len(line) > 5 and 
                any('\u4e00' <= char <= '\u9fff' for char in line) and
                not any(skip in line.lower() for skip in ['info', 'debug', 'error', 'step', 'agent@', 'browser_use'])):
                chinese_lines.append(line)
        
        return '\n'.join(chinese_lines) if chinese_lines else None
    
    async def _ai_process_content(self, raw_content: str, original_question: str) -> str:
        """使用AI智能梳理和规范化内容格式"""
        if not raw_content or not self.llm:
            return raw_content
        
        try:
            process_prompt = f"""
你是一个专业的信息整理专家，需要对搜索结果进行智能梳理和格式规范化。

原始问题：{original_question}

原始搜索结果：
{raw_content}

请按照以下要求整理信息：

1. **语言规范**：除专有名词（如产品名称、公司名称、技术术语等）外，全部使用中文表达
2. **内容梳理**：去除无关信息、重复内容和技术日志
3. **结构优化**：使用清晰的层次结构，如数字列表、要点等
4. **信息完整**：保留所有有价值的核心信息
5. **表达准确**：确保信息准确性，不添加原文中没有的内容

输出要求：
- 直接输出整理后的内容，不要包含"整理结果"等前缀
- 使用规范的中文表达
- 保持逻辑清晰，层次分明
- 专有名词保持原文，其他内容全中文
"""
            
            messages = [UserMessage(content=process_prompt)]
            ai_response = await self.llm.ainvoke(messages)
            
            # 提取AI处理后的内容
            if hasattr(ai_response, 'completion'):
                processed_content = ai_response.completion
            elif hasattr(ai_response, 'content'):
                processed_content = ai_response.content
            elif hasattr(ai_response, 'text'):
                processed_content = ai_response.text
            else:
                processed_content = str(ai_response)
            
            # 如果AI处理失败，返回原始内容
            if not processed_content or len(processed_content.strip()) < 20:
                return self._basic_format_content(raw_content)
            
            return processed_content.strip()
            
        except Exception as e:
            print(f"AI内容处理失败：{e}")
            # 回退到基础格式化
            return self._basic_format_content(raw_content)
    
    def _basic_format_content(self, content: str) -> str:
        """基础内容格式化（当AI处理失败时使用）"""
        if not content:
            return "未获取到有效内容"
        
        # 移除技术日志和无关信息
        lines = content.split('\n')
        clean_lines = []
        
        for line in lines:
            line = line.strip()
            # 过滤掉技术日志、调试信息等
            if (line and len(line) > 5 and 
                not any(skip in line.lower() for skip in 
                        ['info', 'debug', 'error', 'step', 'agent@', 'browser_use', 'result:', 'extracted_content'])):
                clean_lines.append(line)
        
        # 如果清理后内容太少，返回原始内容的后半部分
        if len(clean_lines) < 3:
            all_lines = [line.strip() for line in lines if line.strip()]
            clean_lines = all_lines[-10:] if len(all_lines) > 10 else all_lines
        
        return '\n'.join(clean_lines) if clean_lines else content
    
    def _extract_chinese_from_log(self, log_text: str) -> str:
        """从日志文本中提取中文内容"""
        if not log_text:
            return None
        
        lines = log_text.split('\n')
        result_content = []
        capture_result = False
        
        for line in lines:
            line = line.strip()
            
            if 'Result:' in line and not any(skip in line.lower() for skip in ['step', 'agent@', 'info']):
                result_part = line.split('Result:', 1)[-1].strip()
                if result_part and any('\u4e00' <= char <= '\u9fff' for char in result_part):
                    result_content.append(result_part)
                capture_result = True
                continue
            
            if capture_result:
                if any(marker in line.lower() for marker in ['info', 'debug', 'step', 'agent@', 'next goal']):
                    break
                if line and len(line) > 5 and any('\u4e00' <= char <= '\u9fff' for char in line):
                    result_content.append(line)
        
        if result_content:
            return '\n'.join(result_content)
        
        # 备用方案
        chinese_lines = []
        for line in lines:
            line = line.strip()
            if (line and len(line) > 10 and 
                any('\u4e00' <= char <= '\u9fff' for char in line) and
                not any(skip in line.lower() for skip in ['info', 'debug', 'error', 'step', 'agent@', 'browser_use'])):
                chinese_lines.append(line)
        
        return '\n'.join(chinese_lines[-5:]) if chinese_lines else None
    
    async def process_execution_result(self, execution_plan: Dict, rating: int, feedback: str = "") -> Dict:
        """处理执行结果和评分"""
        try:
            # 处理评分
            rating_result = await self.rating_system.process_rating(
                rating=rating,
                question=execution_plan["question"],
                execution_steps=self._extract_execution_steps(execution_plan),
                result=execution_plan.get("result", ""),
                task_type=execution_plan["task_type"],
                execution_time=execution_plan.get("execution_time", 0.0),
                feedback=feedback
            )
            
            # 更新执行计划
            execution_plan["rating"] = rating
            execution_plan["feedback"] = feedback
            execution_plan["rating_result"] = rating_result
            execution_plan["processed_at"] = datetime.now().isoformat()
            
            return {
                "success": True,
                "execution_plan": execution_plan,
                "rating_result": rating_result
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "execution_plan": execution_plan
            }
    
    def _extract_execution_steps(self, execution_plan: Dict) -> List[str]:
        """从执行计划中提取执行步骤"""
        steps = []
        
        # 从策略中提取
        strategy = execution_plan.get("execution_strategy", "")
        if strategy:
            lines = strategy.split('\n')
            for line in lines:
                line = line.strip()
                if line and (line.startswith(('1.', '2.', '3.', '4.', '5.')) or 
                           line.startswith(('•', '-', '*'))):
                    steps.append(line)
        
        # 如果没有提取到步骤，使用默认描述
        if not steps:
            steps = [
                f"分析任务：{execution_plan['question']}",
                f"执行策略：{execution_plan['task_type']}类型任务",
                "浏览器自动化执行",
                "提取和整理结果"
            ]
        
        return steps[:99]  # 限制步骤数量
    
    def _is_result_valid(self, result: str, question: str) -> bool:
        """检查结果质量是否合格"""
        if not result or len(result.strip()) < 20:
            return False
        
        # 检查是否包含错误信息
        error_indicators = [
            "未能提取到有效结果", "执行失败", "超时", "错误", 
            "无法访问", "页面加载失败", "未找到相关信息"
        ]
        
        for indicator in error_indicators:
            if indicator in result:
                return False
        
        # 检查是否包含中文内容（针对中文问题）
        if any('\u4e00' <= char <= '\u9fff' for char in question):
            if not any('\u4e00' <= char <= '\u9fff' for char in result):
                return False
        
        # 检查是否包含有效的结构化内容
        # 如果结果包含数字列表或要点，认为是有效的
        if any(pattern in result for pattern in ['1.', '2.', '3.', '•', '-', '*', '：']):
            return True
        
        # 检查内容长度是否合理（降低要求）
        if len(result.strip()) < 30:
            return False
            
        return True
    
    async def _replan_simplified_strategy(self, execution_plan: Dict) -> Dict:
        """重新规划简化策略"""
        question = execution_plan["question"]
        
        # 简化策略
        simplified_strategy = f"""
1. 直接搜索关键词：{question}
2. 点击第一个相关结果
3. 快速提取核心信息
4. 输出简要总结
"""
        
        # 更新执行计划
        execution_plan["execution_strategy"] = simplified_strategy
        execution_plan["estimated_steps"] = min(execution_plan.get("estimated_steps", 5), 4)
        execution_plan["replanned"] = True
        
        return execution_plan
    
    def get_current_execution_status(self) -> Optional[Dict]:
        """获取当前执行状态"""
        if not self.current_execution:
            return None
        
        status = self.current_execution.copy()
        if status.get("start_time"):
            status["elapsed_time"] = time.time() - status["start_time"]
        
        return status
    
    def stop_current_execution(self) -> bool:
        """停止当前执行"""
        if self.current_execution:
            self.current_execution["status"] = "stopped"
            self.current_execution["end_time"] = time.time()
            if self.current_execution.get("start_time"):
                self.current_execution["execution_time"] = (
                    self.current_execution["end_time"] - self.current_execution["start_time"]
                )
            self.current_execution = None
            return True
        return False