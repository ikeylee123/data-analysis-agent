import streamlit as st
import pandas as pd
from pathlib import Path
from agents.file_parser import FileParserAgent
from agents.data_analyzer import DataAnalyzerAgent
from agents.report_generator import ReportGeneratorAgent
from utils.chart_generator import ChartGenerator
from config import Config
import os

# 页面配置
st.set_page_config(
    page_title="数据分析Agent系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 初始化目录
os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
os.makedirs(Config.REPORT_DIR, exist_ok=True)

st.title("📊 企业数据分析Agent系统")
st.markdown("---")

# 侧边栏菜单
with st.sidebar:
    st.header("🔧 系统菜单")
    page = st.radio(
        "选择功能",
        ["📤 数据上传", "📈 数据分析", "📋 报告生成", "📊 仪表板"]
    )

# 初始化Session State
if 'uploaded_file_path' not in st.session_state:
    st.session_state.uploaded_file_path = None
if 'analysis_results' not in st.session_state:
    st.session_state.analysis_results = None
if 'df' not in st.session_state:
    st.session_state.df = None

# 页面1: 数据上传
if page == "📤 数据上传":
    st.header("数据上传")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("上传企业数据")
        uploaded_file = st.file_uploader(
            "选择文件 (CSV, Excel, PDF)",
            type=['csv', 'xlsx', 'xls', 'pdf']
        )
        
        if uploaded_file is not None:
            file_path = os.path.join(Config.UPLOAD_DIR, uploaded_file.name)
            
            with open(file_path, 'wb') as f:
                f.write(uploaded_file.getbuffer())
            
            st.session_state.uploaded_file_path = file_path
            st.success(f"✅ 文件上传成功: {uploaded_file.name}")
            
            # 显示文件预览
            try:
                if uploaded_file.name.endswith('.csv'):
                    preview_df = pd.read_csv(file_path)
                else:
                    preview_df = pd.read_excel(file_path)
                
                st.session_state.df = preview_df
                
                st.subheader("数据预览")
                st.dataframe(preview_df.head(10), use_container_width=True)
                
                st.info(f"📊 数据形状: {preview_df.shape[0]} 行 × {preview_df.shape[1]} 列")
                st.info(f"📋 列名: {', '.join(preview_df.columns)}")
            except Exception as e:
                st.error(f"预览失败: {str(e)}")
    
    with col2:
        st.subheader("上传说明")
        st.markdown("""
        ### 支持的文件格式:
        - 📄 **CSV** - 逗号分隔的文本文件
        - 📊 **Excel** - .xlsx 或 .xls 格式
        - 📑 **PDF** - 便携式文档格式
        
        ### 文件要求:
        - 最大文件大小: 50 MB
        - 建议包含表头行
        - 数据格式规范
        
        ### 常见数据类型:
        - 销售数据
        - 用户行为数据
        - 财务数据
        - 产品数据
        """)

# 页面2: 数据分析
elif page == "📈 数据分析":
    st.header("数据分析")
    
    if st.session_state.df is None:
        st.warning("⚠️ 请先在'数据上传'页面上传文件")
    else:
        df = st.session_state.df
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("数据统计")
            st.dataframe(df.describe(), use_container_width=True)
        
        with col2:
            st.subheader("分析选项")
            analysis_type = st.selectbox(
                "选择分析类型",
                ["基本统计", "相关性分析", "数据分布", "异常检测"]
            )
            
            if st.button("🔍 开始分析", use_container_width=True):
                with st.spinner("分析中..."):
                    try:
                        analyzer = DataAnalyzerAgent()
                        results = analyzer.run(
                            st.session_state.uploaded_file_path,
                            analysis_type
                        )
                        st.session_state.analysis_results = results
                        st.success("✅ 分析完成!")
                    except Exception as e:
                        st.error(f"分析失败: {str(e)}")
        
        # 图表生成
        st.subheader("可视化分析")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        col1, col2 = st.columns(2)
        
        with col1:
            if len(numeric_cols) >= 2:
                x_col = st.selectbox("X轴", numeric_cols, key="x1")
                y_col = st.selectbox("Y轴", numeric_cols, key="y1")
                chart_type = st.radio("图表类型", ["柱状图", "折线图", "散点图"])
                
                if st.button("生成图表"):
                    try:
                        if chart_type == "柱状图":
                            fig = ChartGenerator.create_bar_chart(
                                df, x_col, y_col, f"{x_col} vs {y_col}"
                            )
                        elif chart_type == "折线图":
                            fig = ChartGenerator.create_line_chart(
                                df, x_col, y_col, f"{x_col} vs {y_col}"
                            )
                        else:
                            fig = ChartGenerator.create_scatter_chart(
                                df, x_col, y_col, f"{x_col} vs {y_col}"
                            )
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"图表生成失败: {str(e)}")
        
        with col2:
            st.info("💡 选择数值列创建可视化图表，更好地理解数据特征")

# 页面3: 报告生成
elif page == "📋 报告生成":
    st.header("智能报告生成")
    
    if st.session_state.analysis_results is None:
        st.warning("⚠️ 请先完成数据分析")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("自定义需求")
            user_requirements = st.text_area(
                "请输入您对报告的具体需求",
                placeholder="例如: 生成一份关于销售趋势的报告，重点分析按地区的销售额",
                height=150
            )
        
        with col2:
            st.subheader("报告配置")
            report_format = st.selectbox("报告格式", ["HTML", "PDF", "Markdown"])
            include_charts = st.checkbox("包含图表", value=True)
            include_recommendations = st.checkbox("包含建议", value=True)
        
        if st.button("📝 生成报告", use_container_width=True):
            with st.spinner("正在生成报告..."):
                try:
                    report_gen = ReportGeneratorAgent()
                    report = report_gen.run(
                        st.session_state.analysis_results,
                        user_requirements
                    )
                    
                    st.success("✅ 报告生成成功!")
                    st.markdown("---")
                    st.subheader("报告内容预览")
                    st.markdown(report['content'])
                    
                    # 下载按钮
                    st.download_button(
                        label="⬇️ 下载报告",
                        data=report['content'],
                        file_name=f"报告_{report['timestamp']}.txt",
                        mime="text/plain"
                    )
                except Exception as e:
                    st.error(f"报告生成失败: {str(e)}")

# 页面4: 仪表板
elif page == "📊 仪表板":
    st.header("数据仪表板")
    
    if st.session_state.df is None:
        st.warning("⚠️ 请先在'数据上传'页面上传文件")
    else:
        df = st.session_state.df
        
        # KPI指标
        st.subheader("关键指标 (KPI)")
        
        numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
        
        if numeric_cols:
            cols = st.columns(len(numeric_cols[:4]))  # 最多显示4个
            
            for idx, col in enumerate(numeric_cols[:4]):
                with cols[idx]:
                    st.metric(
                        label=col,
                        value=f"{df[col].sum():,.2f}",
                        delta=f"平均: {df[col].mean():,.2f}"
                    )
        
        st.markdown("---")
        
        # 详细数据表
        st.subheader("完整数据表")
        st.dataframe(df, use_container_width=True)

# 页脚
st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
    <p>🚀 企业数据分析Agent系统 | 由LangChain + Streamlit驱动</p>
    </div>
    """,
    unsafe_allow_html=True
)
