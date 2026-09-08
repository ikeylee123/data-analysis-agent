import os

import pandas as pd
import streamlit as st

from agents.data_analyzer import DataAnalyzerAgent
from agents.report_generator import ReportGeneratorAgent
from config import Config
from utils.chart_generator import ChartGenerator
from utils.file_handler import FileHandler


ROLE_LABELS = {
    "sales": "销售额",
    "profit": "利润",
    "discount": "折扣",
    "quantity": "数量",
    "region": "地区",
    "category": "品类",
    "segment": "客群",
    "product": "产品",
    "customer": "客户",
    "date": "日期",
    "order": "订单",
}


def metric_label(metric: str) -> str:
    labels = {
        "record_count": "记录数",
        "total_sales": "总销售额",
        "average_sales": "平均销售额",
        "total_profit": "总利润",
        "profit_margin_percent": "利润率",
        "total_quantity": "总数量",
        "average_discount_percent": "平均折扣",
        "order_count": "订单数",
        "average_order_value": "平均订单金额",
    }
    return labels.get(metric, metric)


def format_number(value):
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return value


def show_risk_results(risks: dict):
    st.write("风险异常用于提示需要进一步复盘的地方，不等同于最终问题结论。")

    loss_records = risks.get("loss_records", {})
    high_discount_loss = risks.get("high_discount_loss_records", {})
    numeric_outliers = risks.get("numeric_outliers", [])
    high_missing = risks.get("high_missing_columns", [])

    cols = st.columns(4)
    cols[0].metric("亏损记录数", f"{loss_records.get('count', 0):,}")
    cols[1].metric("亏损合计", format_number(loss_records.get("total_loss", 0)))
    cols[2].metric("高折扣亏损记录", f"{high_discount_loss.get('count', 0):,}")
    cols[3].metric("异常字段数", f"{len(numeric_outliers):,}")

    if loss_records.get("count", 0) > 0:
        st.warning(
            f"发现 {loss_records['count']:,} 条亏损记录，亏损合计 {format_number(loss_records.get('total_loss', 0))}。"
            "建议按产品、地区、客户和折扣进一步拆解原因。"
        )

    if high_discount_loss.get("count", 0) > 0:
        threshold = high_discount_loss.get("discount_threshold")
        st.warning(
            f"发现 {high_discount_loss['count']:,} 条高折扣且亏损的记录。"
            f"当前高折扣阈值约为 {threshold:.2%}。这通常用于检查促销策略是否侵蚀利润。"
        )

    if numeric_outliers:
        st.write("数值异常字段")
        st.caption("异常值通常代表极大或极小的记录，可能是大客户订单、特殊促销、录入错误或真实业务波动。")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "字段": item["column"],
                        "异常数量": item["outlier_count"],
                        "建议解读": "优先抽样检查极端记录是否合理",
                    }
                    for item in numeric_outliers
                ]
            ),
            use_container_width=True,
            hide_index=True,
        )

    if high_missing:
        st.write("缺失值较高字段")
        st.dataframe(pd.DataFrame(high_missing), use_container_width=True, hide_index=True)

    if not any([loss_records, high_discount_loss, numeric_outliers, high_missing]):
        st.info("暂未发现明显风险或异常。")


def show_top_bottom_results(top_bottom: dict):
    st.subheader("贡献与拖累分析")
    st.write(
        "这部分用于回答两个问题：哪些维度贡献最大，哪些维度表现最低。"
        "对销售额而言，Top 代表主要收入来源，Bottom 多数是长尾低销量对象；"
        "对利润而言，Bottom 更值得关注，因为它可能代表亏损或利润拖累。"
    )

    for metric, dimensions in top_bottom.items():
        metric_meaning = (
            "主要收入贡献与长尾低销量"
            if "Sales" in metric or "sales" in metric.lower()
            else "利润贡献与利润拖累"
        )
        st.write(f"**指标：{metric}（{metric_meaning}）**")

        for dimension, values in dimensions.items():
            with st.expander(f"{dimension} 维度", expanded=False):
                col_top, col_bottom = st.columns(2)
                with col_top:
                    st.write("贡献最高 Top 10")
                    st.caption("用于识别核心增长来源、重点客户/产品/地区。")
                    st.dataframe(pd.DataFrame(values.get("top", [])), use_container_width=True, hide_index=True)
                with col_bottom:
                    title = "表现最低 Bottom 10"
                    caption = "销售额低不一定是坏事，可能只是长尾；利润低则更可能需要复盘。"
                    st.write(title)
                    st.caption(caption)
                    st.dataframe(pd.DataFrame(values.get("bottom", [])), use_container_width=True, hide_index=True)


def show_analysis_results(results: dict):
    overview = results.get("overview", {})
    schema = results.get("schema", {})
    roles = results.get("field_roles", {})
    kpis = results.get("kpis", {})
    risks = results.get("risks", {})

    st.subheader("数据概览")
    cols = st.columns(4)
    cols[0].metric("行数", f"{overview.get('row_count', 0):,}")
    cols[1].metric("列数", f"{overview.get('column_count', 0):,}")
    cols[2].metric("重复行", f"{overview.get('duplicate_rows', 0):,}")
    cols[3].metric("数值列", f"{len(schema.get('numeric_columns', [])):,}")

    st.subheader("字段识别")
    role_rows = [
        {"业务角色": ROLE_LABELS.get(role, role), "识别字段": column or "未识别"}
        for role, column in roles.items()
    ]
    st.dataframe(pd.DataFrame(role_rows), use_container_width=True, hide_index=True)

    if kpis:
        st.subheader("核心 KPI")
        kpi_items = list(kpis.items())
        metric_cols = st.columns(min(4, len(kpi_items)))
        for idx, (key, value) in enumerate(kpi_items[:8]):
            with metric_cols[idx % len(metric_cols)]:
                st.metric(metric_label(key), format_number(value))

    tab_overview, tab_numeric, tab_category, tab_trends, tab_risks = st.tabs(
        ["分析摘要", "数值分析", "分类分析", "时间趋势", "风险异常"]
    )

    with tab_overview:
        st.write(results.get("result", ""))
        missing = overview.get("missing_values", {})
        if missing:
            st.write("缺失值字段")
            st.dataframe(
                pd.DataFrame(
                    [{"字段": column, "缺失数量": count} for column, count in missing.items()]
                ),
                use_container_width=True,
                hide_index=True,
            )
        st.write("样本行")
        st.dataframe(pd.DataFrame(results.get("sample_rows", [])), use_container_width=True)

    with tab_numeric:
        numeric_analysis = results.get("numeric_analysis", {})
        if numeric_analysis:
            rows = [{"字段": column, **details} for column, details in numeric_analysis.items()]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
        else:
            st.info("没有可用于数值分析的字段。")

    with tab_category:
        category_analysis = results.get("category_analysis", {})
        if category_analysis:
            for dimension, details in category_analysis.items():
                st.write(f"**{dimension}**")
                if details.get("top_values"):
                    st.dataframe(pd.DataFrame(details["top_values"]), use_container_width=True, hide_index=True)
                if details.get("top_by_metric"):
                    st.caption("按核心指标聚合 Top 10")
                    st.dataframe(pd.DataFrame(details["top_by_metric"]), use_container_width=True, hide_index=True)
        else:
            st.info("没有可用于分类分析的字段。")

    with tab_trends:
        trends = results.get("time_trends", {})
        rows = trends.get("rows", []) if isinstance(trends, dict) else []
        if rows:
            trend_df = pd.DataFrame(rows)
            st.dataframe(trend_df, use_container_width=True, hide_index=True)
            metric_cols = [column for column in trend_df.columns if column not in {"_period"}]
            if "_period" in trend_df.columns and metric_cols:
                st.line_chart(trend_df.set_index("_period")[metric_cols])
        else:
            st.info("未识别到可用于时间趋势分析的日期字段。")

    with tab_risks:
        if risks:
            show_risk_results(risks)
        else:
            st.info("暂未发现明显风险或异常。")

    top_bottom = results.get("top_bottom", {})
    if top_bottom:
        show_top_bottom_results(top_bottom)


st.set_page_config(
    page_title="企业数据分析 Agent 系统",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
os.makedirs(Config.REPORT_DIR, exist_ok=True)

st.title("📊 企业数据分析 Agent 系统")
st.markdown("---")

with st.sidebar:
    st.header("系统菜单")
    page = st.radio(
        "选择功能",
        ["数据上传", "数据分析", "报告生成", "仪表板"],
    )

if "uploaded_file_path" not in st.session_state:
    st.session_state.uploaded_file_path = None
if "analysis_results" not in st.session_state:
    st.session_state.analysis_results = None
if "business_insights" not in st.session_state:
    st.session_state.business_insights = None
if "df" not in st.session_state:
    st.session_state.df = None


if page == "数据上传":
    st.header("数据上传")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("上传企业数据")
        uploaded_file = st.file_uploader(
            "选择文件（CSV、Excel、PDF）",
            type=["csv", "xlsx", "xls", "pdf"],
        )

        if uploaded_file is not None:
            file_path = FileHandler.save_uploaded_file(uploaded_file)
            st.session_state.uploaded_file_path = file_path
            st.success(f"文件上传成功：{uploaded_file.name}")

            try:
                preview_df = FileHandler.read_file(file_path)
                st.session_state.df = preview_df
                st.session_state.analysis_results = None
                st.session_state.business_insights = None

                st.subheader("数据预览")
                st.dataframe(preview_df.head(10), use_container_width=True)
                st.info(f"数据形状：{preview_df.shape[0]} 行 × {preview_df.shape[1]} 列")
                st.info(f"列名：{', '.join(preview_df.columns)}")
            except Exception as e:
                st.error(f"预览失败：{str(e)}")

    with col2:
        st.subheader("上传说明")
        st.markdown(
            """
            ### 支持的文件格式
            - **CSV**：逗号分隔文本文件
            - **Excel**：.xlsx 或 .xls 文件
            - **PDF**：便携式文档格式

            ### 文件要求
            - 最大文件大小：50 MB
            - 建议包含表头行
            - 建议使用结构化表格数据

            ### 分析方式
            系统会先在本地识别字段、计算 KPI、发现风险，再将结构化摘要交给 Gemini 生成报告。
            """
        )

elif page == "数据分析":
    st.header("数据分析")

    if st.session_state.df is None:
        st.warning("请先在“数据上传”页面上传文件。")
    else:
        df = st.session_state.df

        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader("数据预览")
            st.dataframe(df.head(20), use_container_width=True)
        with col2:
            st.subheader("分析选项")
            analysis_type = st.selectbox(
                "选择分析类型",
                ["综合业务分析", "基本统计", "相关性分析", "数据分布", "异常检测"],
            )
            if st.button("开始分析", use_container_width=True):
                with st.spinner("正在进行字段识别和结构化分析..."):
                    try:
                        analyzer = DataAnalyzerAgent()
                        st.session_state.analysis_results = analyzer.run(
                            st.session_state.uploaded_file_path,
                            analysis_type,
                        )
                        st.success("分析完成。")
                    except Exception as e:
                        st.error(f"分析失败：{str(e)}")

        if st.session_state.analysis_results:
            show_analysis_results(st.session_state.analysis_results)

        st.subheader("自定义可视化")
        numeric_cols = df.select_dtypes(include=["number"]).columns.tolist()
        if len(numeric_cols) >= 2:
            col1, col2 = st.columns(2)
            with col1:
                x_col = st.selectbox("X 轴", numeric_cols, key="x1")
                y_col = st.selectbox("Y 轴", numeric_cols, key="y1")
                chart_type = st.radio("图表类型", ["柱状图", "折线图", "散点图"])
                if st.button("生成图表"):
                    try:
                        if chart_type == "柱状图":
                            fig = ChartGenerator.create_bar_chart(df, x_col, y_col, f"{x_col} vs {y_col}")
                        elif chart_type == "折线图":
                            fig = ChartGenerator.create_line_chart(df, x_col, y_col, f"{x_col} vs {y_col}")
                        else:
                            fig = ChartGenerator.create_scatter_chart(df, x_col, y_col, f"{x_col} vs {y_col}")
                        st.plotly_chart(fig, use_container_width=True)
                    except Exception as e:
                        st.error(f"图表生成失败：{str(e)}")
            with col2:
                st.info("这里保留手动图表探索。后续可以增加自动图表推荐。")
        else:
            st.info("当前数据中至少需要两个数值列才能生成图表。")

elif page == "报告生成":
    st.header("智能报告生成")

    report_input = st.session_state.business_insights or st.session_state.analysis_results

    if report_input is None:
        st.warning("请先完成数据分析。")
    else:
        col1, col2 = st.columns([2, 1])

        with col1:
            st.subheader("自定义需求")
            user_requirements = st.text_area(
                "请输入你对报告的具体需求",
                placeholder="例如：生成一份销售趋势报告，重点分析不同地区的销售额和利润表现。",
                height=150,
            )

        with col2:
            st.subheader("报告配置")
            st.selectbox("报告格式", ["Markdown", "HTML", "PDF"])
            st.checkbox("包含图表", value=True)
            st.checkbox("包含建议", value=True)
            st.markdown("### Report Settings")
            report_language = st.selectbox("Language", ["Chinese", "English"])
            report_tone = st.selectbox("Tone", ["Executive Summary", "Analyst Report"])
            report_length = st.selectbox("Length", ["Brief", "Detailed"])

        if st.button("生成报告", use_container_width=True):
            with st.spinner("正在生成报告..."):
                try:
                    report_gen = ReportGeneratorAgent()
                    report = report_gen.run(
                        report_input,
                        user_requirements,
                        report_settings={
                            "language": report_language,
                            "tone": report_tone,
                            "length": report_length,
                        },
                    )

                    st.success("报告生成成功。")
                    source_labels = {
                        "gemini": "Gemini",
                        "gemini_repaired": "Gemini repaired",
                        "local": "Local template",
                    }
                    source_label = source_labels.get(report.get("source"), report.get("source", "Unknown"))
                    st.caption(f"Report source: {source_label}")
                    if report.get("source") == "local" and report.get("fallback_reason"):
                        st.warning(
                            "Gemini 输出未通过安全格式检查，已使用本地模板生成报告。"
                            f"原因：{report['fallback_reason']}"
                        )
                    st.markdown("---")
                    st.subheader("报告内容预览")
                    st.markdown(report["content"])

                    st.download_button(
                        label="下载报告",
                        data=report["content"],
                        file_name=f"report_{report['timestamp']}.txt",
                        mime="text/plain",
                    )
                except Exception as e:
                    st.error(f"报告生成失败：{str(e)}")

elif page == "仪表板":
    st.header("数据仪表板")

    if st.session_state.df is None:
        st.warning("请先在“数据上传”页面上传文件。")
    else:
        df = st.session_state.df
        if st.session_state.analysis_results:
            show_analysis_results(st.session_state.analysis_results)
        else:
            st.info("请先到“数据分析”页面运行一次分析，仪表板将展示结构化结果。")

        st.markdown("---")
        st.subheader("完整数据表")
        st.dataframe(df, use_container_width=True)

st.markdown("---")
st.markdown(
    """
    <div style='text-align: center'>
    <p>企业数据分析 Agent 系统 | 由 LangChain + Streamlit 驱动</p>
    </div>
    """,
    unsafe_allow_html=True,
)
