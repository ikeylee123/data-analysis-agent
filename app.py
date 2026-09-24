import hashlib
import os
import re

import pandas as pd
import plotly.express as px
import streamlit as st

from agents.data_analyzer import DataAnalyzerAgent
from agents.report_generator import ReportGeneratorAgent
from config import Config
from utils.i18n import display_label, domain_label, resolve_report_language, t
from utils.chart_generator import ChartGenerator
from utils.file_handler import FileHandler
from utils.ui_helpers import (
    format_business_value,
    format_kpi_card_value,
    format_segment_table,
    humanize_label,
    humanize_report_markdown_labels,
    normalized_domain,
    plotly_key,
    prepare_chart_data,
    primary_kpi_cards,
    recommend_chart_type,
    relevant_field_mapping,
    reliability_status_items,
    report_content_for_display,
    risk_cards,
    sanitize_technical_reason,
    time_aggregation_for,
)
from utils.session_state import (
    init_session_state,
    reset_all_state,
    set_analysis_config,
    set_dataset_state,
    set_report_config,
    set_current_page,
    store_analysis_result,
    store_report_result,
    set_ui_language,
)


def show_primary_kpis(results: dict, language: str) -> None:
    st.subheader(t("analytics.core_kpis", language))
    columns = st.columns(5)
    for column, card in zip(columns, primary_kpi_cards(results, language)):
        column.metric(card["label"], format_kpi_card_value(card["value"], card["format"]))


def show_domain_charts(df: pd.DataFrame, results: dict, language: str) -> None:
    st.subheader(t("analytics.performance", language))
    domain = normalized_domain(results)
    figures = []
    if domain == "retail":
        roles = results.get("field_roles", {})
        category, region = roles.get("category"), roles.get("region")
        sales, profit, discount = roles.get("sales"), roles.get("profit"), roles.get("discount")
        if category and sales and profit:
            grouped = df.groupby(category, dropna=False)[[sales, profit]].sum().reset_index()
            figures.append(("sales_profit_category", px.bar(grouped, x=category, y=[sales, profit], barmode="group", title=t("chart.retail_category", language), labels={c: display_label(c, language) for c in [category, sales, profit]})))
        if region and profit:
            grouped = df.groupby(region, dropna=False)[profit].sum().reset_index().sort_values(profit, ascending=False)
            figures.append(("profit_region", px.bar(grouped, x=region, y=profit, title=t("chart.retail_region", language), labels={region: display_label(region, language), profit: display_label(profit, language)})))
        if discount and profit:
            figures.append(("discount_profit", px.scatter(df, x=discount, y=profit, title=t("chart.retail_discount", language), hover_data=[category] if category else None, labels={discount: display_label(discount, language), profit: display_label(profit, language)})))
    elif domain == "saas" and {"month", "mrr", "plan_type", "churn_rate"}.issubset(df.columns):
        dated = df.assign(_period=pd.to_datetime(df["month"], errors="coerce")).dropna(subset=["_period"])
        trend = dated.groupby("_period", as_index=False)["mrr"].sum().sort_values("_period")
        figures.append(("mrr_trend", px.line(trend, x="_period", y="mrr", markers=True, title=t("chart.saas_mrr", language), labels={"mrr": display_label("mrr", language)})))
        latest = dated.loc[dated["_period"].eq(dated["_period"].max())]
        plan_mrr = latest.groupby("plan_type", as_index=False)["mrr"].sum().sort_values("mrr", ascending=False)
        figures.append(("mrr_by_plan", px.bar(plan_mrr, x="plan_type", y="mrr", title=t("chart.saas_plan_mrr", language), labels={"plan_type": display_label("plan_type", language), "mrr": display_label("mrr", language)})))
        plan_churn = df.groupby("plan_type", as_index=False)["churn_rate"].mean()
        plan_churn["churn_rate_percent"] = plan_churn["churn_rate"] * 100
        figures.append(("churn_by_plan", px.bar(plan_churn, x="plan_type", y="churn_rate_percent", title=t("chart.saas_plan_churn", language), labels={"plan_type": display_label("plan_type", language), "churn_rate_percent": display_label("churn_rate_percent", language)})))
    elif domain == "logistics" and {"carrier", "region", "delay_flag", "damage_flag", "delivery_time_days"}.issubset(df.columns):
        carrier = df.groupby("carrier", as_index=False).agg(delay_rate=("delay_flag", "mean"), average_delivery_time=("delivery_time_days", "mean"))
        carrier["delay_rate_percent"] = carrier["delay_rate"] * 100
        figures.append(("delay_carrier", px.bar(carrier, x="carrier", y="delay_rate_percent", title=t("chart.logistics_delay", language), labels={"carrier": display_label("carrier", language), "delay_rate_percent": display_label("delay_rate", language)})))
        figures.append(("delivery_carrier", px.bar(carrier, x="carrier", y="average_delivery_time", title=t("chart.logistics_delivery", language), labels={"carrier": display_label("carrier", language), "average_delivery_time": display_label("average_delivery_time", language)})))
        region = df.groupby("region", as_index=False)["damage_flag"].mean()
        region["damage_rate_percent"] = region["damage_flag"] * 100
        figures.append(("damage_region", px.bar(region, x="region", y="damage_rate_percent", title=t("chart.logistics_damage", language), labels={"region": display_label("region", language), "damage_rate_percent": display_label("damage_rate", language)})))
    if not figures:
        st.info(t("analytics.no_trends", language)); return
    first, second = st.columns(2)
    with first: st.plotly_chart(figures[0][1], use_container_width=True, key=plotly_key(domain, "main", figures[0][0]))
    if len(figures) > 1:
        with second: st.plotly_chart(figures[1][1], use_container_width=True, key=plotly_key(domain, "main", figures[1][0]))
    if len(figures) > 2: st.plotly_chart(figures[2][1], use_container_width=True, key=plotly_key(domain, "main", figures[2][0]))


def show_overview_summary(results: dict, df: pd.DataFrame, language: str) -> None:
    domain = normalized_domain(results); roles = results.get("field_roles", {})
    overview, generic = results.get("overview", {}), results.get("kpis", {})
    industry = results.get("industry_analysis", {}); kpis, segments = industry.get("kpis", {}), industry.get("segments", {})
    st.markdown(f"#### {t('analytics.dataset_summary', language)}")
    if domain == "retail":
        facts = [t("analytics.records", language, count=f"{overview.get('row_count', len(df)):,}")]
        for role, key in (("category", "overview.columns"), ("region", "analytics.regions"), ("segment", "analytics.customer_segments")):
            column = roles.get(role)
            if column: facts.append(t(key, language, count=f"{df[column].nunique():,}") if key != "overview.columns" else f"{df[column].nunique():,} {display_label(role, language)}")
        signals = [f"{display_label('total_sales', language)}: {format_business_value('sales', generic.get('total_sales'))}", f"{display_label('total_profit', language)}: {format_business_value('profit', generic.get('total_profit'))}", f"{display_label('profit_margin_percent', language)}: {format_kpi_card_value(generic.get('profit_margin_percent'), 'percent_number')}"]
    elif domain == "saas":
        facts = [t("analytics.observations", language, count=f"{overview.get('row_count', len(df)):,}"), t("analytics.months", language, count=df['month'].nunique()), t("analytics.plans", language, count=df['plan_type'].nunique()), t("analytics.customer_segments", language, count=df['customer_segment'].nunique())]
        plan = segments.get("plan_type", {})
        signals = [f"{display_label('current_mrr', language)}: {format_business_value('mrr', kpis.get('current_mrr'))}", f"{display_label('mrr_growth_percent', language)}: {format_kpi_card_value(kpis.get('mrr_growth_percent'), 'percent_number')}", t("analytics.highest_churn", language, name=plan.get('risk_by_churn', {}).get('plan_type', 'N/A')), t("analytics.largest_mrr", language, name=plan.get('best_by_mrr', {}).get('plan_type', 'N/A'))]
    else:
        dates = pd.to_datetime(df.get("date"), errors="coerce"); period = "N/A" if dates.dropna().empty else f"{dates.min().date()} to {dates.max().date()}"
        facts = [t("analytics.shipments", language, count=f"{kpis.get('total_shipments', len(df)):,}"), t("analytics.carriers", language, count=df['carrier'].nunique()), t("analytics.regions", language, count=df['region'].nunique()), t("analytics.time_coverage", language, period=period)]
        carrier = segments.get("carrier", {}).get("risk_by_delay", {})
        signals = [f"{display_label('delay_rate', language)}: {format_business_value('delay_rate', kpis.get('delay_rate'))}", f"{display_label('damage_rate', language)}: {format_business_value('damage_rate', kpis.get('damage_rate'))}", f"{display_label('average_delivery_time_days', language)}: {format_business_value('average_delivery_time_days', kpis.get('average_delivery_time_days'))}", t("analytics.operational_review", language, name=carrier.get('carrier', display_label('carrier', language)))]
    st.write(" · ".join(facts)); st.markdown(f"#### {t('analytics.operational_signals' if domain == 'logistics' else 'analytics.business_signals', language)}")
    for signal in signals: st.markdown(f"- {signal}")


def show_top_bottom_results(top_bottom: dict, language: str) -> None:
    st.write(t("analytics.long_tail_note", language))
    for metric, dimensions in top_bottom.items():
        for dimension, values in dimensions.items():
            with st.expander(t("analytics.by", language, metric=humanize_label(metric, language), dimension=humanize_label(dimension, language)), expanded=False):
                top, bottom = st.columns(2)
                with top: st.write(t("analytics.top", language)); st.dataframe(format_segment_table(values.get("top", []), [dimension, metric], language), use_container_width=True, hide_index=True)
                with bottom: st.write(t("analytics.bottom", language)); st.dataframe(format_segment_table(values.get("bottom", []), [dimension, metric], language), use_container_width=True, hide_index=True)


def show_segments(results: dict, language: str) -> None:
    domain = normalized_domain(results)
    if domain == "retail": show_top_bottom_results(results.get("top_bottom", {}), language); return
    segments = results.get("industry_analysis", {}).get("segments", {})
    dimensions = ["plan_type", "customer_segment"] if domain == "saas" else ["carrier", "region"]
    columns = {"saas": ["mrr", "arr", "churn_rate", "new_customers", "churned_customers", "expansion_revenue"], "logistics": ["shipment_count", "delay_rate", "damage_rate", "average_delivery_time_days", "average_shipping_cost"]}
    for dimension in dimensions:
        rows = segments.get(dimension, {}).get("rows", [])
        if rows: st.markdown(f"#### {t('analytics.by', language, metric='', dimension=humanize_label(dimension, language))}"); st.dataframe(format_segment_table(rows, [dimension] + columns[domain], language), use_container_width=True, hide_index=True)


def show_trends(results: dict, df: pd.DataFrame, language: str) -> None:
    domain = normalized_domain(results)
    if domain == "retail":
        roles = results.get("field_roles", {}); date, sales, profit = roles.get("date"), roles.get("sales"), roles.get("profit")
        if date and sales and profit:
            dated = df.assign(_period=pd.to_datetime(df[date], errors="coerce")).dropna(subset=["_period"]); trend = dated.groupby(dated["_period"].dt.to_period("M").astype(str))[[sales, profit]].sum().reset_index()
            fig=px.line(trend, x="_period", y=[sales, profit], markers=True, title=t("chart.retail_trend", language), labels={sales: display_label(sales, language), profit: display_label(profit, language)})
            st.plotly_chart(fig, use_container_width=True, key=plotly_key("retail", "trends", "sales_profit")); strongest=trend.loc[trend[sales].idxmax(),"_period"]; weakest=trend.loc[trend[sales].idxmin(),"_period"]
            st.write(t("analytics.strongest_month", language, strongest=strongest, weakest=weakest)); st.caption(t("analytics.limited_months", language, count=len(trend))); return
    if domain == "saas" and {"month", "mrr", "new_customers", "churned_customers"}.issubset(df.columns):
        dated=df.assign(_period=pd.to_datetime(df["month"], errors="coerce")).dropna(subset=["_period"]); trend=dated.groupby("_period",as_index=False).agg(mrr=("mrr","sum"),new_customers=("new_customers","sum"),churned_customers=("churned_customers","sum")).sort_values("_period")
        st.plotly_chart(px.line(trend,x="_period",y="mrr",markers=True,title=t("chart.saas_mrr",language),labels={"mrr":display_label("mrr",language)}),use_container_width=True,key=plotly_key("saas","trends","mrr")); st.plotly_chart(px.line(trend,x="_period",y=["new_customers","churned_customers"],markers=True,title=t("chart.saas_customers",language)),use_container_width=True,key=plotly_key("saas","trends","customer_movement"))
        growth=results["industry_analysis"]["kpis"].get("mrr_growth_percent"); st.write(t("analytics.mrr_change",language,start=f"{trend.iloc[0]['mrr']:,.2f}",end=f"{trend.iloc[-1]['mrr']:,.2f}",growth=f"{growth:.2f}")); return
    if domain == "logistics" and {"date","delay_flag","delivery_time_days"}.issubset(df.columns):
        dated=df.assign(_period=pd.to_datetime(df["date"],errors="coerce")).dropna(subset=["_period"]); trend=dated.groupby(dated["_period"].dt.to_period("M").astype(str)).agg(shipments=("delay_flag","count"),delay_rate=("delay_flag","mean"),avg_delivery_time=("delivery_time_days","mean")).reset_index()
        st.plotly_chart(px.line(trend,x="_period",y=["delay_rate","avg_delivery_time"],markers=True,title=t("chart.logistics_trend",language)),use_container_width=True,key=plotly_key("logistics","trends","operations")); st.caption(t("analytics.limited_time",language)); return
    st.info(t("analytics.no_trends",language))


def show_correlations(df: pd.DataFrame, results: dict, language: str) -> None:
    numeric=df.select_dtypes(include=["number"]).copy()
    if numeric.shape[1] < 2: st.info(t("analytics.need_numeric",language)); return
    domain=normalized_domain(results); corr=numeric.corr().round(3); labels=[humanize_label(c,language) for c in corr.columns]
    st.plotly_chart(px.imshow(corr,x=labels,y=labels,color_continuous_scale="RdBu_r",zmin=-1,zmax=1,text_auto=".2f",title=t("chart.correlation",language)),use_container_width=True,key=plotly_key(domain,"correlations","heatmap"))
    candidates=[]
    for i,left in enumerate(corr.columns):
        for right in corr.columns[i+1:]:
            if domain=="saas" and {left,right}=={"mrr","arr"}: continue
            value=corr.loc[left,right]
            if pd.notna(value): candidates.append((abs(value),value,left,right))
    for _,value,left,right in sorted(candidates,reverse=True)[:3]: st.markdown("- "+t("analytics.correlation_line",language,left=humanize_label(left,language),right=humanize_label(right,language),direction=t("analytics.positive" if value>=0 else "analytics.negative",language),value=f"{value:.2f}"))
    if domain=="saas" and {"mrr","arr"}.issubset(corr.columns): st.caption(t("analytics.deterministic_arr",language))
    st.caption(t("analytics.correlation_warning",language))
    with st.expander(t("analytics.technical_matrix",language)): st.dataframe(corr,use_container_width=True)


def show_domain_risks(results: dict, language: str) -> None:
    cards=risk_cards(results,language); columns=st.columns(len(cards))
    for column,card in zip(columns,cards): column.metric(card["label"],card["value"])
    domain,risks=normalized_domain(results),results.get("risks",{})
    if domain=="retail" and risks.get("high_discount_loss_records",{}).get("count",0): st.warning(t("analytics.discount_note",language,threshold=f"{risks['high_discount_loss_records'].get('discount_threshold',0):.2%}"))
    if domain=="saas": st.info(t("analytics.saas_risk_note",language))
    if domain=="logistics": st.info(t("analytics.logistics_risk_note",language))
    anomalies=risks.get("numeric_outliers",[])
    if anomalies: st.markdown(f"#### {t('analytics.secondary_anomalies',language)}"); st.dataframe(pd.DataFrame([{t("analytics.field",language):humanize_label(i["column"],language),t("analytics.outlier_count",language):i["outlier_count"]} for i in anomalies]),use_container_width=True,hide_index=True)


def show_advanced_exploration(df: pd.DataFrame, domain: str, language: str) -> None:
    with st.expander(t("advanced.title",language),expanded=False):
        numeric=df.select_dtypes(include=["number"]).columns.tolist()
        if not numeric: st.info(t("advanced.no_numeric",language)); return
        x_options=df.columns.tolist() if len(numeric)>1 else [c for c in df.columns if c not in numeric]
        if not x_options: st.info(t("advanced.need_two",language)); return
        x=st.selectbox(t("advanced.x",language),x_options,key="advanced_x",format_func=lambda value:humanize_label(value,language)); y_options=[c for c in numeric if c!=x]
        if not y_options: st.info(t("advanced.choose_x",language)); return
        y=st.selectbox(t("advanced.y",language),y_options,key="advanced_y",format_func=lambda value:humanize_label(value,language)); chart_type,error=recommend_chart_type(df,x,y)
        if error: st.warning(error); return
        aggregation=time_aggregation_for(y) if chart_type=="line" else "mean" if chart_type=="bar" else None; prepared=prepare_chart_data(df,x,y,chart_type)
        if aggregation=="sum": title=t("chart.total_over",language,metric=humanize_label(y,language),dimension=humanize_label(x,language))
        elif aggregation=="mean": title=t("chart.average_over",language,metric=humanize_label(y,language),dimension=humanize_label(x,language))
        else: title=t("chart.vs",language,x=humanize_label(x,language),y=humanize_label(y,language))
        figure=ChartGenerator.create_line_chart(prepared,x,y,title) if chart_type=="line" else ChartGenerator.create_bar_chart(prepared,x,y,title) if chart_type=="bar" else ChartGenerator.create_scatter_chart(prepared,x,y,title)
        st.plotly_chart(figure,use_container_width=True,key=plotly_key("advanced",domain,x,y,chart_type))


def show_business_analytics(results: dict, df: pd.DataFrame, language: str) -> None:
    show_primary_kpis(results,language); show_domain_charts(df,results,language)
    tabs=st.tabs([t(f"tab.{name}",language) for name in ("overview","segments","trends","correlations","risks")])
    with tabs[0]: show_overview_summary(results,df,language)
    with tabs[1]: show_segments(results,language)
    with tabs[2]: show_trends(results,df,language)
    with tabs[3]: show_correlations(df,results,language)
    with tabs[4]: show_domain_risks(results,language)
    show_advanced_exploration(df,normalized_domain(results),language)


def render_generated_report(report: dict, language: str) -> None:
    statuses=reliability_status_items(report,language); columns=st.columns(len(statuses))
    for column,(label,value) in zip(columns,statuses):
        with column: st.caption(label); st.markdown(f"**{value}**")
    source=report.get("source"); provider=report.get("provider_status"); fallback_reason=report.get("fallback_reason")
    if source=="gemini_repaired": st.info(t("reliability.repaired_message",language))
    elif source=="local" and provider=="rate_limited": st.warning(t("reliability.rate_message",language))
    elif source=="local" and provider=="unavailable": st.warning(t("reliability.unavailable_message",language))
    elif source=="local" and provider=="configuration_error": st.warning(t("reliability.config_message",language))
    elif source=="local" and report.get("report_validation_status")=="failed": st.warning(t("reliability.validation_message",language))
    if source=="local" and fallback_reason:
        with st.expander(t("report.technical",language)): st.code(sanitize_technical_reason(fallback_reason))
    st.markdown("---"); st.subheader(t("report.preview",language))
    content=report_content_for_display(humanize_report_markdown_labels(report["content"]),hide_fallback_error=source=="local" and provider!="available")
    st.markdown(content); st.download_button(t("report.download",language),content,file_name=f"report_{report['timestamp']}.txt",mime="text/plain",key="download_report_button")

st.set_page_config(
    page_title="Business Insight Copilot",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

init_session_state(st.session_state)

os.makedirs(Config.UPLOAD_DIR, exist_ok=True)
os.makedirs(Config.REPORT_DIR, exist_ok=True)

language = st.session_state.ui_language
with st.sidebar:
    st.caption(t("sidebar.language", language))
    selected_language = st.radio(
        "UI language", ["en", "zh"],
        format_func=lambda value: "English" if value == "en" else "中文",
        horizontal=True, key="ui_language_selector", label_visibility="collapsed",
    )
    set_ui_language(st.session_state, selected_language)
    language = selected_language
    st.header(t("sidebar.menu", language))
    if st.button(t("sidebar.start_new", language), use_container_width=True, key="start_new_analysis_button"):
        reset_all_state(st.session_state)
        st.rerun()
    page_selection = st.radio(
        "Application page", ["overview", "analytics", "report"],
        format_func=lambda value: t(f"nav.{value}", language),
        key="current_page_selector", label_visibility="collapsed",
    )
    set_current_page(st.session_state, page_selection)
    page = st.session_state.current_page

st.title(t("app.title", language))
st.caption(t("app.subtitle", language))
st.markdown("---")

if page == "overview":
    st.header(t("nav.overview", language))
    col1, col2 = st.columns(2)
    with col1:
        st.subheader(t("overview.upload_title", language))
        uploaded_file = st.file_uploader(t("overview.upload_label", language), type=["csv", "xlsx", "xls"], key=f"dataset_uploader_{st.session_state.upload_widget_version}")
        if uploaded_file is not None:
            signature = hashlib.sha256(uploaded_file.getvalue()).hexdigest()
            if signature != st.session_state.uploaded_file_signature:
                try:
                    file_path = FileHandler.save_uploaded_file(uploaded_file)
                    preview_df = FileHandler.read_file(file_path)
                    analyzer = DataAnalyzerAgent(); analyzer.df = preview_df
                    schema = analyzer.infer_schema(); field_mapping = analyzer.infer_field_roles(schema); overview = analyzer.build_overview()
                    set_dataset_state(st.session_state, signature=signature, filename=uploaded_file.name, file_path=file_path, dataframe=preview_df, detected_domain=analyzer.detect_industry(schema), field_mapping=field_mapping, data_overview=overview)
                    st.success(t("overview.upload_success", language, filename=uploaded_file.name))
                except Exception as exc:
                    st.error(t("overview.upload_error", language, error=str(exc)))
        if st.session_state.uploaded_df is not None:
            preview_df = st.session_state.uploaded_df
            domain = normalized_domain(None, st.session_state.detected_domain)
            st.subheader(t("overview.preview", language))
            st.caption(f"{t('overview.current_dataset', language)}: {st.session_state.uploaded_filename} · {t('overview.detected_domain', language)}: {domain_label(domain, language)}")
            st.dataframe(preview_df.head(10), use_container_width=True)
            overview = st.session_state.data_overview or {}; metadata_columns = st.columns(3)
            metadata_columns[0].metric(t("overview.rows", language), f"{overview.get('row_count', len(preview_df)):,}")
            metadata_columns[1].metric(t("overview.columns", language), f"{overview.get('column_count', len(preview_df.columns)):,}")
            metadata_columns[2].metric(t("overview.duplicates", language), f"{overview.get('duplicate_rows', 0):,}")
            st.markdown(f"**{t('overview.detected_domain', language)}:** `{domain_label(domain, language)}`")
            with st.expander(t("overview.details", language)): st.write(t("overview.column_list", language, columns=", ".join(preview_df.columns)))
            st.subheader(t("overview.quality", language)); missing_values = overview.get("missing_values", {})
            if missing_values:
                st.dataframe(pd.DataFrame([{t("overview.missing_column", language): column, t("overview.missing_values", language): count} for column, count in missing_values.items()]), use_container_width=True, hide_index=True)
            else: st.success(t("overview.no_missing", language))
            st.subheader(t("overview.mapping", language))
            mapping_rows, other_columns = relevant_field_mapping(domain, preview_df.columns.tolist(), st.session_state.field_mapping or {}, language)
            st.dataframe(pd.DataFrame(mapping_rows), use_container_width=True, hide_index=True)
            if other_columns: st.caption(t("overview.other", language, columns=", ".join(other_columns)))
    with col2:
        st.subheader(t("overview.instructions", language))
        st.markdown(f"### {t('overview.formats', language)}\n- {t('overview.csv', language)}\n- {t('overview.excel', language)}\n\n### {t('overview.requirements', language)}\n- {t('overview.max_size', language)}\n- {t('overview.header', language)}\n- {t('overview.structured', language)}\n\n### {t('overview.method', language)}\n{t('overview.method_text', language)}")

elif page == "analytics":
    st.header(t("nav.analytics", language))
    if st.session_state.uploaded_df is None:
        st.warning(t("analytics.upload_first", language))
    else:
        df = st.session_state.uploaded_df
        analysis_type = "comprehensive_business_analysis"
        set_analysis_config(st.session_state, analysis_type)
        if st.session_state.analysis_result is None:
            st.info(t("analytics.ready", language))
        if st.button(t("analytics.run", language), type="primary", key="run_analysis_button"):
            with st.spinner(t("analytics.running", language)):
                try:
                    result = DataAnalyzerAgent().run(st.session_state.uploaded_file_path, analysis_type)
                    store_analysis_result(st.session_state, result, analysis_type)
                    st.success(t("analytics.success", language))
                except Exception as exc:
                    st.error(t("analytics.failure", language, error=str(exc)))
        if st.session_state.analysis_result is not None:
            show_business_analytics(st.session_state.analysis_result, df, language)

elif page == "report":
    st.header(t("nav.report", language))
    report_input = st.session_state.analysis_result
    if report_input is None:
        st.warning(t("report.analyze_first", language))
    else:
        existing_config = st.session_state.report_config or {"user_requirements": "", "language_choice": "follow_ui", "tone": "Executive Summary", "length": "Brief"}
        if "language_choice" not in existing_config:
            legacy = existing_config.get("language")
            existing_config = {**existing_config, "language_choice": "zh" if legacy == "Chinese" else "en" if legacy == "English" else "follow_ui"}
        col1, col2 = st.columns([2, 1])
        with col1:
            st.subheader(t("report.requirements", language))
            user_requirements = st.text_area(t("report.requirements_label", language), value=existing_config.get("user_requirements", ""), placeholder=t("report.requirements_placeholder", language), height=150, key="report_requirements_input")
        with col2:
            st.subheader(t("report.settings", language))
            st.selectbox(t("report.format", language), ["Markdown"], key="report_format_selector")
            language_options = ["follow_ui", "en", "zh"]
            language_choice = st.selectbox(t("report.language", language), language_options, index=language_options.index(existing_config.get("language_choice", "follow_ui")), format_func=lambda value: t({"follow_ui": "report.follow_ui", "en": "report.english", "zh": "report.chinese"}[value], language), key="report_language_selector")
            tone_options = ["Executive Summary", "Analyst Report"]
            report_tone = st.selectbox(t("report.tone", language), tone_options, index=tone_options.index(existing_config.get("tone", "Executive Summary")), format_func=lambda value: t("report.executive" if value == "Executive Summary" else "report.analyst", language), key="report_tone_selector")
            length_options = ["Brief", "Detailed"]
            report_length = st.selectbox(t("report.length", language), length_options, index=length_options.index(existing_config.get("length", "Brief")), format_func=lambda value: t("report.brief" if value == "Brief" else "report.detailed", language), key="report_length_selector")
        report_config = {"user_requirements": user_requirements, "language_choice": language_choice, "tone": report_tone, "length": report_length}
        set_report_config(st.session_state, report_config)
        if st.button(t("report.generate", language), use_container_width=True, key="generate_report_button"):
            with st.spinner(t("report.generating", language)):
                try:
                    resolved_language = resolve_report_language(language_choice, language)
                    report_gen = ReportGeneratorAgent()
                    report_schema = report_gen.build_report_schema(report_input, user_requirements)
                    report = report_gen.run(report_input, user_requirements, report_settings={"language": resolved_language, "tone": report_tone, "length": report_length})
                    store_report_result(st.session_state, report=report, report_schema=report_schema, config=report_config)
                    st.success(t("report.success", language))
                except Exception as exc:
                    st.error(t("report.failure", language, error=str(exc)))
        if st.session_state.generated_report is not None:
            render_generated_report(st.session_state.generated_report, language)

st.markdown("---")
st.markdown(f"<div style='text-align: center'><p>{t('app.footer', language)}</p></div>", unsafe_allow_html=True)
