
import streamlit as st
import time

from src.agent.core import DevAgent 

# 1. 网页标题与极客风配置
st.set_page_config(page_title="DevAgent 智能研发助手", page_icon="🤖", layout="centered")
st.title("🤖 DevAgent 私有代码库智能体")
st.caption("🚀 具备 RAG 检索、AST 扫描、多轮记忆的复合型 AI 系统")

# 2. 会话状态管理 (Session State) —— 极其重要！
# 因为 Streamlit 每次用户点击都会重新从上往下跑一遍代码
# 我们必须把 Agent 实例和历史聊天记录“锁”在内存里
if "agent" not in st.session_state:
    # 初始化你的 Agent（包含向量库预热）
    with st.spinner("正在预热 Agent 引擎与向量检索中枢..."):
        st.session_state.agent = DevAgent(max_history_turns=4)
    st.session_state.messages = [] # 用于前端显示的聊天记录

# 3. 渲染历史聊天气泡
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# 4. 监听用户输入
if prompt := st.chat_input("请问有什么可以帮您？(如：分析一下 core.py 的逻辑)"):
    
    # 立即在前端显示用户的提问
    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.messages.append({"role": "user", "content": prompt})

    # 5. 呼叫后端 Agent 并展示“思考特效”
    with st.chat_message("assistant"):
        # 👑 炫酷的 Agent 思考状态框
        with st.status("Agent 正在深度思考与调用工具...", expanded=True) as status:
            st.write("🧠 综合分析意图中...")
            
            # 记录开始时间
            start_time = time.perf_counter()
            
            # 🔥 呼叫你的底层逻辑！
            final_response = st.session_state.agent.chat(prompt)
            
            # 计算耗时
            elapsed_time = time.perf_counter() - start_time
            
            # 状态框变绿打钩
            status.update(label=f"思考完毕！(耗时 {elapsed_time:.2f} 秒)", state="complete", expanded=False)
        
        # 打印最终的人话
        st.markdown(final_response)
        
    # 把大模型的回答存入前端记忆区
    st.session_state.messages.append({"role": "assistant", "content": final_response})