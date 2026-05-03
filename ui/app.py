"""
StudyHelper - Streamlit Web UI
"""
import json
import logging
import os
import sys
import time

import streamlit as st

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from agent.core import Agent
from agent.llm_client import LLMClient
from tools.executor import create_bridge
from config import OUTPUT_DIR, build_system_prompt

logging.basicConfig(level=logging.WARNING)

st.set_page_config(
    page_title="知识学习智能助手",
    page_icon="📚",
    layout="wide",
    initial_sidebar_state="expanded",
)

if "messages" not in st.session_state:
    st.session_state.messages = []
if "agent" not in st.session_state:
    st.session_state.agent = None
if "bridge" not in st.session_state:
    st.session_state.bridge = None
if "running" not in st.session_state:
    st.session_state.running = False
if "steps" not in st.session_state:
    st.session_state.steps = []


@st.cache_resource
def init_agent():
    bridge = create_bridge()
    llm = LLMClient()

    def on_step(event_type, name, detail):
        step_info = {
            "time": time.time(),
            "type": event_type,
            "name": name,
            "detail": detail,
        }
        st.session_state.steps.append(step_info)

    agent = Agent(
        llm=llm,
        tool_schemas=bridge.get_all_schemas(),
        tool_executor=bridge.execute,
        on_step=on_step,
        system_prompt=build_system_prompt(),
    )
    return agent, bridge


st.title("📚 知识学习智能助手")
st.caption("输入你想学的知识，Agent 自动搜索资料、编撰教材、生成练习题")

with st.sidebar:
    st.header("⚙️ 设置")
    topic = st.text_area(
        "🎯 学习主题",
        placeholder="例如：微积分入门、Python面向对象编程、机器学习基础...",
        height=100,
    )

    st.divider()
    st.markdown("### 🛠 工作流程")
    st.markdown("""
    1. 🔍 **搜索资料** - 搜索相关网页
    2. 📥 **抓取内容** - 获取文章正文
    3. 📝 **编撰教材** - 组织成教学书
    4. ✍️ **生成练习** - 配套练习题
    5. 💾 **保存成果** - 保存为文件
    """)

    st.divider()
    st.markdown("### 技术栈")
    st.markdown("""
    - **Function Call**: LLM 工具调用
    - **Skills**: 提示词技能模块
    - **MCP**: Model Context Protocol
    """)

    run_button = st.button("🚀 开始学习", type="primary", use_container_width=True)


if run_button and topic.strip():
    st.session_state.running = True
    st.session_state.steps = []
    st.session_state.messages = []

    agent, bridge = init_agent()
    st.session_state.agent = agent
    st.session_state.bridge = bridge

    status_container = st.empty()
    progress_container = st.empty()
    result_container = st.empty()

    with status_container:
        with st.spinner("Agent 正在工作中..."):
            result = agent.run(topic.strip())

    st.session_state.running = False
    st.session_state.result = result

    steps = st.session_state.steps
    if steps:
        with st.expander("🔍 查看 Agent 执行步骤", expanded=False):
            for step in steps:
                if step["type"] == "tool_start":
                    st.info(f"🔧 **调用工具**: `{step['name']}`")
                    try:
                        args = json.loads(step["detail"])
                        st.json(args)
                    except Exception:
                        st.text(step["detail"])
                elif step["type"] == "tool_end":
                    st.success(f"✅ **{step['name']}** 执行完成")

    st.markdown("---")
    st.markdown("## 📖 生成结果")

    tab1, tab2 = st.tabs(["📖 教材内容", "💾 输出文件"])

    with tab1:
        st.markdown(result)

    with tab2:
        st.markdown("### 输出文件目录")
        output_path = os.path.abspath(OUTPUT_DIR)
        st.code(f"📁 {output_path}")
        if os.path.exists(output_path):
            files = os.listdir(output_path)
            if files:
                for f in files:
                    filepath = os.path.join(output_path, f)
                    with open(filepath, "r", encoding="utf-8") as fh:
                        content = fh.read()
                    st.download_button(
                        label=f"📥 下载 {f}",
                        data=content,
                        file_name=f,
                        mime="text/markdown" if f.endswith(".md") else "text/plain",
                    )
            else:
                st.info("暂无输出文件（Agent 可能未调用保存工具）")

elif run_button and not topic.strip():
    st.warning("请输入学习主题")

st.divider()

col1, col2 = st.columns(2)
with col1:
    if st.button("🔄 重新开始"):
        st.session_state.messages = []
        st.session_state.steps = []
        st.session_state.running = False
        st.session_state.result = None
        st.rerun()

with col2:
    st.markdown(
        "<div style='text-align:right;color:gray;padding-top:6px'>"
        "Made with ❤️ for learning | Agent = Function Call + Skills + MCP"
        "</div>",
        unsafe_allow_html=True,
    )
