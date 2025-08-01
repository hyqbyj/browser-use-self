from browser_use.llm import ChatDeepSeek
from browser_use import Agent
from browser_use.browser import BrowserProfile, BrowserSession
from browser_use.llm.messages import UserMessage
from dotenv import load_dotenv
import os
import gradio as gr
import asyncio
import time

# 导入长期记忆模块
from memory.memory_manager import MemoryManager
from memory.strategy_store import StrategyStore
from memory.rating_system import RatingSystem
from memory.task_executor import TaskExecutor

load_dotenv()

# 检查DeepSeek API密钥是否存在
deepseek_api_key = os.getenv('DEEPSEEK_API_KEY')
if deepseek_api_key is None:
    print('请确保设置了DEEPSEEK_API_KEY环境变量:')
    print('export DEEPSEEK_API_KEY=your_key')
    exit(0)

# 初始化DeepSeek LLM
llm = ChatDeepSeek(
    base_url='https://api.deepseek.com/v1',
    model='deepseek-chat',
    api_key=deepseek_api_key,
)

# 初始化长期记忆系统
print("正在初始化长期记忆系统...")
memory_manager = MemoryManager(llm=llm)
strategy_store = StrategyStore(memory_manager)
rating_system = RatingSystem(memory_manager)
task_executor = TaskExecutor(llm, memory_manager, strategy_store, rating_system)
print("长期记忆系统初始化完成")

# 检测Edge浏览器路径
def find_edge_path():
    """查找本地Edge浏览器的安装路径"""
    possible_paths = [
        'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
        'C:\\Users\\{}\\AppData\\Local\\Microsoft\\Edge\\Application\\msedge.exe'.format(os.getenv('USERNAME', 'User'))
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"找到Edge浏览器：{path}")
            return path
    
    print("警告：未找到Edge浏览器，将使用默认Chromium")
    return None

# 配置Edge浏览器 - 优化等待时间参数解决识别框和跟进速度问题
edge_path = find_edge_path()
browser_profile = BrowserProfile(
    executable_path=edge_path,  # Edge浏览器路径（如果找到）
    headless=False,  # 显示浏览器界面
    viewport={'width': 1280, 'height': 720},
    user_data_dir=None,  # 使用临时目录避免锁定问题
     # 优化等待时间参数，解决登录后识别框不动和页面切换跟进慢的问题
    wait_between_actions=2.0,  # 增加动作间等待时间到2秒，确保页面元素稳定
    wait_for_network_idle_page_load_time=4.0,  # 增加网络空闲等待时间到4秒，确保页面完全加载
    maximum_wait_page_load_time=20.0,  # 增加最大页面加载等待时间到20秒
    minimum_wait_page_load_time=3.0,  # 设置最小页面加载等待时间为3秒，增大页面加载到彩色框出现的时间
    
    args=[
        '--disable-blink-features=AutomationControlled',
        '--no-sandbox',
        '--disable-gpu',
        '--disable-extensions',  # 禁用扩展
        '--disable-plugins',
        # '--disable-images',  # 启用图片加载以支持更好的页面元素识别
        '--disable-javascript-harmony-shipping',
        '--disable-background-timer-throttling',
        '--disable-backgrounding-occluded-windows',
        '--disable-renderer-backgrounding',
        '--disable-features=TranslateUI',
        '--disable-ipc-flooding-protection',
        '--disable-default-apps',
        '--disable-sync',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-web-security',
        '--disable-features=VizDisplayCompositor',
        '--aggressive-cache-discard',
        '--memory-pressure-off'  # 关闭内存压力检测
    ]
)
# 全局浏览器会话，支持重复使用
browser_session = None

def get_browser_session():
    """获取或创建浏览器会话"""
    global browser_session
    if browser_session is None:
        browser_session = BrowserSession(
            browser_profile=browser_profile,
            keep_alive=True  # 保持会话，支持重复使用
        )
    return browser_session

def close_browser_session():
    """关闭当前浏览器会话"""
    global browser_session
    if browser_session is not None:
        try:
            # 这里可以添加关闭浏览器的逻辑
            browser_session = None
            return "浏览器会话已关闭，下次搜索将创建新会话"
        except Exception as e:
            return f"关闭浏览器时出现错误：{str(e)}"
    else:
        return "当前没有活动的浏览器会话"


def create_gradio_interface():
    """创建Gradio前端界面"""
    import time
    
    with gr.Blocks(title="智能浏览器助手", theme=gr.themes.Soft()) as interface:
        gr.Markdown("""
        # ⭐智能浏览器助手
        **核心功能特性：**
        - **智能记忆系统**：自动学习并记录成功的执行策略
        - **任务智能分析**：结合历史经验分析任务并生成最佳执行方案
        - **自动化执行**：基于记忆优化的策略自动执行浏览器任务
        - **质量评价机制**：对执行结果进行评分，四星及以上自动收录到记忆库
        - **持续学习优化**：通过用户反馈不断改进执行策略和效果
        
        **⏰ 安全保护机制：** 任务执行超过二十分钟将自动终止并输出已获得的部分结果
        """)
        
        with gr.Row():
            with gr.Column(scale=2):
                question_input = gr.Textbox(
                    label="请输入您的任务需求",
                    placeholder="智能助手将结合记忆系统分析您的需求并生成最佳执行策略。\n\n任务示例：\n- 最新的人工智能发展趋势有哪些，列出五点\n- 在GitHub上查找最热门的Python机器学习项目\n- 比较三种主流云服务提供商的价格和功能特性\n- 搜索并总结关于Web3技术的最新发展动态",
                    lines=4,
                    value=""
                )
                
                search_btn = gr.Button("🧠 智能分析执行方案", variant="primary", size="lg")
                
                with gr.Row():
                    stop_btn = gr.Button("⏹️ 停止任务执行", variant="stop", size="sm", visible=False)
                    close_btn = gr.Button("🔄 重置浏览器会话", variant="secondary", size="sm")
                    memory_stats_btn = gr.Button("📊 记忆系统统计", variant="secondary", size="sm")
                
                # 执行状态显示
                status_display = gr.Textbox(
                    label="任务执行状态",
                    value="等待任务输入中...",
                    interactive=False,
                    max_lines=1
                )
                
                # 任务执行步骤显示
                steps_display = gr.Textbox(
                    label="智能分析的执行步骤",
                    placeholder="智能助手分析任务后，详细执行步骤将在这里显示，您可以查看和修改...",
                    lines=8,
                    interactive=True
                )
                
                confirm_steps_btn = gr.Button("✅ 确认步骤并开始执行", variant="primary", visible=False)
                
            with gr.Column(scale=3):
                result_output = gr.Textbox(
                    label="任务执行结果",
                    lines=15,
                    interactive=False,
                    show_copy_button=True,
                    placeholder="智能助手的任务执行结果将在这里显示..."
                )
                
                # 评分系统
                with gr.Group(visible=False) as rating_group:
                    gr.Markdown("### ⭐ 结果评价")
                    rating_radio = gr.Radio(
                        choices=[
                            ("⭐⭐⭐⭐⭐ 完美执行", 5),
                            ("⭐⭐⭐⭐ 良好执行", 4),
                            ("⭐⭐⭐ 一般执行", 3),
                            ("⭐⭐ 较差执行", 2),
                            ("⭐ 失败执行", 1)
                        ],
                        label="执行结果评分（一至五星）",
                        info="四星及以上的优质结果将被自动收录到记忆系统中"
                    )
                    
                    feedback_input = gr.Textbox(
                        label="反馈意见（可选）",
                        placeholder="您可以提供改进建议或其他反馈...",
                        lines=2
                    )
                    
                    submit_rating_btn = gr.Button("📝 提交评分反馈", variant="primary")
                
                # 收录状态显示
                collection_status = gr.Textbox(
                    label="评分反馈信息",
                    visible=False,
                    interactive=False
                )
        
        # 存储当前执行结果
        current_execution_result = gr.State(None)
        
        # 1. 分析任务并显示步骤
        def analyze_task(question):
            if not question.strip():
                return "请输入有效的任务需求", "", "等待任务输入...", gr.update(visible=False)
            
            try:
                # 分析任务
                execution_plan = asyncio.run(task_executor.analyze_task(question))
                
                # 提取并格式化详细执行步骤
                execution_strategy = execution_plan.get('execution_strategy', '')
                
                # 解析执行步骤
                formatted_steps = ""
                if execution_strategy and execution_strategy.strip():
                    # 按行分割并格式化
                    lines = execution_strategy.split('\n')
                    step_lines = []
                    for line in lines:
                        line = line.strip()
                        if line and (line[0].isdigit() or line.startswith(('•', '-', '*'))):
                            step_lines.append(line)
                    
                    if step_lines:
                        formatted_steps = "\n".join(step_lines)
                    else:
                        # 如果没有找到标准格式的步骤，直接使用原始内容
                        formatted_steps = execution_strategy
                else:
                    formatted_steps = "暂无详细执行步骤"
                
                # 构建步骤显示文本 - 只显示具体步骤
                steps_text = formatted_steps if formatted_steps and formatted_steps != "暂无详细执行步骤" else "暂无详细执行步骤"
                
                return (
                    execution_plan,  # 存储到state
                    steps_text,      # 显示步骤
                    "✅ 智能分析完成，请确认执行步骤",  # 状态
                    gr.update(visible=True)  # 显示确认按钮
                )
                
            except Exception as e:
                return (
                    None,
                    f"任务分析失败：{str(e)}",
                    "❌ 智能分析失败",
                    gr.update(visible=False)
                )
        
        # 2. 执行任务
        def execute_task(execution_plan, modified_steps):
            if not execution_plan:
                return "没有可执行的任务计划", "❌ 任务执行失败", gr.update(visible=False), None
            
            try:
                # 提取用户修改的步骤
                if modified_steps and modified_steps.strip():
                    # 直接使用修改后的步骤文本
                    lines = modified_steps.split('\n')
                    extracted_steps = []
                    
                    # 提取所有步骤行
                    for line in lines:
                        line = line.strip()
                        # 提取步骤行（以数字开头或特殊符号开头）
                        if line and (line[0].isdigit() or line.startswith(('•', '-', '*'))):
                            extracted_steps.append(line)
                    
                    # 如果提取到步骤，更新执行计划
                    if extracted_steps:
                        execution_plan['execution_strategy'] = '\n'.join(extracted_steps)
                        print(f"用户修改的执行步骤：\n{execution_plan['execution_strategy']}")
                
                # 执行任务 - 直接调用 task_executor.execute_task
                current_browser_session = get_browser_session()
                if not current_browser_session:
                    return "无法建立浏览器连接，请检查浏览器配置", "❌ 浏览器连接失败", gr.update(visible=False), None
                
                print(f"🚀 开始执行任务...类型：{execution_plan.get('task_type', 'unknown')}，预估步骤：{execution_plan.get('estimated_steps', 0)}")
                execution_result = asyncio.run(task_executor.execute_task(execution_plan, current_browser_session))
                
                # 处理结果
                result_text = execution_result.get('result', '任务执行完成但未获取到结果内容')
                
                # 添加执行信息
                if execution_result.get('status') == 'timeout':
                    result_text += "\n\n⏰ 注意：任务执行超过二十分钟已自动终止"
                elif execution_result.get('status') == 'failed':
                    result_text += f"\n\n❌ 执行失败：{execution_result.get('error', '未知错误')}"
                
                execution_time = execution_result.get('execution_time', 0)
                result_text += f"\n\n📊 任务执行用时：{int(execution_time//60):02d}分{int(execution_time%60):02d}秒"
                
                # 确保execution_result包含必要信息
                execution_result['question'] = execution_plan.get('question', '')
                
                # 判断执行状态
                if execution_result:
                    status = execution_result.get('status', 'unknown')
                    if status == 'completed':
                        status_text = "✅ 任务执行完成"
                        show_rating = True
                    elif status == 'timeout':
                        status_text = "⏰ 任务执行超时终止"
                        show_rating = True
                    elif status == 'failed':
                        status_text = "❌ 任务执行失败"
                        show_rating = False
                    else:
                        status_text = "⚠️ 任务执行状态未知"
                        show_rating = False
                else:
                    status_text = "❌ 任务执行异常"
                    show_rating = False
                
                return (
                    result_text,
                    status_text,
                    gr.update(visible=show_rating),
                    execution_result
                )
                
            except Exception as e:
                return (
                    f"任务执行异常：{str(e)}",
                    "❌ 任务执行异常",
                    gr.update(visible=False),
                    None
                )
        
        # 3. 处理评分
        def submit_rating(rating, feedback, execution_result):
            if not execution_result or not rating:
                return "请先完成任务执行并选择评分", gr.update(visible=False)
            
            try:
                # 处理评分
                rating_result = asyncio.run(
                    task_executor.process_execution_result(
                        execution_result, rating, feedback
                    )
                )
                
                if rating_result['success']:
                    message = rating_result['rating_result']['message']
                    if rating >= 4:
                        message += "\n\n🎉 评分反馈已成功记录！"
                    return message, gr.update(visible=True)
                else:
                    return f"评分处理失败：{rating_result.get('error', '未知错误')}", gr.update(visible=True)
                    
            except Exception as e:
                return f"评分处理异常：{str(e)}", gr.update(visible=True)
        
        # 4. 获取记忆统计
        def get_memory_stats():
            try:
                stats = rating_system.format_rating_stats_for_display()
                return stats
            except Exception as e:
                return f"获取记忆系统统计信息失败：{str(e)}"
        
        # 5. 关闭浏览器
        def close_browser():
            status = close_browser_session()
            return status
        
        # 绑定事件
        search_btn.click(
            fn=analyze_task,
            inputs=[question_input],
            outputs=[current_execution_result, steps_display, status_display, confirm_steps_btn]
        )
        
        confirm_steps_btn.click(
            fn=execute_task,
            inputs=[current_execution_result, steps_display],
            outputs=[result_output, status_display, rating_group, current_execution_result]
        )
        
        submit_rating_btn.click(
            fn=submit_rating,
            inputs=[rating_radio, feedback_input, current_execution_result],
            outputs=[collection_status, collection_status]
        )
        
        memory_stats_btn.click(
            fn=get_memory_stats,
            outputs=[result_output]
        )
        
        close_btn.click(
            fn=close_browser,
            outputs=[status_display]
        )
        
        # 添加示例问题（多样化的任务类型）
        gr.Examples(
            examples=[
                ["最新的人工智能发展趋势有哪些，列出三点，每点不超过五十字"],
                ["比较GPT-4o和DeepSeek-V3的价格和功能特性"],
                ["帮我在京东上搜索最新款的iPhone，查看价格和用户评价"],
                ["访问GitHub，搜索并分析最热门的三个Python机器学习项目"],
                ["在知乎上查找关于程序员职业发展的讨论，总结主要观点"],
                ["搜索并对比三种流行的前端框架的优缺点"],
                ["查找最新的Web开发技术趋势，列出三点，每点不超过五十字"]
            ],
            inputs=[question_input]
        )
    
    return interface

if __name__ == "__main__":
    # 创建并启动Gradio界面
    demo = create_gradio_interface()
    demo.launch(
        server_name="127.0.0.1",
        server_port=7860,
        show_error=True,
        share=False
    )