# -*- coding: utf-8 -*-
"""
问卷数据一体化处理平台 
整合所有模块：数据接入、无效筛查、图表生成、报告导出
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st

# ==========================================
# 跨平台路径配置 - 确保云端运行
# ==========================================
try:
    WORKSPACE_DIR = Path(__file__).resolve().parent
except Exception:
    WORKSPACE_DIR = Path.cwd()

# 统一使用应用程序目录下的子目录
TEMP_DIR = WORKSPACE_DIR / "temp_uploads"
OUTPUT_DIR = WORKSPACE_DIR / "integrated_output"
CHARTS_DIR = OUTPUT_DIR / "charts"

# 确保所有目录存在
for dir_path in [TEMP_DIR, OUTPUT_DIR, CHARTS_DIR]:
    dir_path.mkdir(parents=True, exist_ok=True)

# 添加路径
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

print(f"[INFO] Platform: {sys.platform}")
print(f"[INFO] Workspace: {WORKSPACE_DIR}")
print(f"[INFO] Temp Dir: {TEMP_DIR}")
print(f"[INFO] Output Dir: {OUTPUT_DIR}")

from questionnaire_platform_core import (
    AI_PROVIDER_PRESETS,
    build_survey_report,
    generate_ai_analysis,
    process_questionnaire,
    save_report_outputs,
    calculate_sample,
)
from integrated_reporting_system import (
    ComprehensiveAnalyzer,
    ReportExporter,
    ChartConfig,
    CHART_COLORS,
)
from group2_invalid_questionnaire_screening1 import normalize_dataframe, infer_columns


st.set_page_config(page_title="问卷数据一体化处理平台", layout="wide")
st.title("📊 问卷数据一体化处理平台")
st.caption("一次完成数据接入、标准化、无效问卷筛查、图表生成、报告导出")

if "comprehensive_report" not in st.session_state:
    st.session_state["comprehensive_report"] = None
if "chart_output_dir" not in st.session_state:
    st.session_state["chart_output_dir"] = None


with st.sidebar:
    st.subheader("⚙️ AI 接口配置（可选）")
    provider_name = st.selectbox("服务商", list(AI_PROVIDER_PRESETS.keys()), index=0)
    provider_preset = AI_PROVIDER_PRESETS[provider_name]
    api_key = st.text_input("API Key", type="password")
    base_url = st.text_input("Base URL", value=provider_preset.get("base_url", ""))
    model = st.text_input("模型名", value=provider_preset.get("model", ""))
    user_requirement = st.text_area("补充要求", placeholder="例如：按课程论文风格生成...")

    st.divider()
    st.subheader("🎨 图表配置")
    color_scheme = st.selectbox("配色方案", list(CHART_COLORS.keys()), index=1)
    chart_dpi = st.slider("图表分辨率", 72, 300, 150, step=12)
    chart_width = st.slider("图表宽度(英寸)", 8, 16, 12)

    st.divider()
    st.subheader("📥 报告导出")
    export_markdown = st.checkbox("Markdown报告", value=True)
    export_json = st.checkbox("JSON报告", value=True)
    export_csv = st.checkbox("CSV统计表", value=True)
    export_excel = st.checkbox("Excel综合报告", value=True)


st.divider()
st.subheader("📐 样本量测算")


col_c1, col_c2 = st.columns(2)
with col_c1:
    conf_input = st.selectbox("置信度", [0.90, 0.95, 0.99], index=1, help="通常选95%")
    margin_input = st.slider("允许误差 (%)", 1, 10, 5, help="调查允许的绝对误差范围")
    p_input = st.slider("预期比例 (p)", 0.1, 0.9, 0.5, help="不确定时选0.5（最保守）")

with col_c2:
    pop_input = st.number_input("总体数量（0=无限总体）", min_value=0, value=10000, step=1000)
    actual_input = st.number_input("实际有效样本数", min_value=0, value=320, step=10)

if st.button("开始测算样本量", type="primary"):
    try:
        res = calculate_sample(
            confidence=conf_input,
            margin_error=margin_input / 100.0,
            p=p_input,
            population=pop_input,
            actual_sample=actual_input,
        )
        st.success(f"✅ 理论最小样本量：**{res['min_sample']}** 份")
        st.info(f"📌 建议发放量：**{res['suggested']}** 份（考虑30%无效问卷）")

        col1, col2, col3 = st.columns(3)
        if res['is_sufficient'] is True:
            col1.success("🎉 实际样本达标")
            col2.info(f"统计精度可靠")
            col3.metric("置信度", f"{conf_input:.0%}")
        elif res['is_sufficient'] is False:
            col1.warning(f"⚠️ 样本不足")
            col2.warning(f"还差 **{res['gap']}** 份")
            col3.metric("所需样本", res['min_sample'])
        else:
            col1.info("💡 请输入实际样本数")

        st.caption("参数影响模拟")
        sim_margin = st.slider("模拟允许误差变化 (%)", 1, 10, 5)
        sim_res = calculate_sample(
            confidence=conf_input,
            margin_error=sim_margin / 100.0,
            p=p_input,
            population=pop_input,
            actual_sample=0,
        )
        st.write(f"当允许误差调整为 {sim_margin}% 时，理论最小样本量为 **{sim_res['min_sample']}** 份")
    except Exception as e:
        st.error(f"计算失败：{e}")


st.divider()
st.subheader("📁 问卷数据处理")


uploaded_file = st.file_uploader(
    "选择 Excel / CSV 文件",
    type=["xlsx", "xls", "xlsm", "csv"],
    help="支持问卷星导出的Excel和CSV格式"
)

output_dir = st.text_input("输出目录", value=str(OUTPUT_DIR))

col_btn1, col_btn2, col_btn3 = st.columns(3)

with col_btn1:
    process_basic = st.button("🔍 基础处理（筛查）", type="primary", use_container_width=True)

with col_btn2:
    process_full = st.button("📊 完整处理（筛查+图表）", type="primary", use_container_width=True)

with col_btn3:
    export_reports = st.button("📥 导出报告", type="primary", use_container_width=True)


if process_basic or process_full:
    if uploaded_file is None:
        st.warning("请先上传文件")
    else:
        try:
            progress = st.progress(0, text="保存上传文件...")
            temp_path = TEMP_DIR / uploaded_file.name
            temp_path.write_bytes(uploaded_file.getvalue())
            print(f"[DEBUG] Uploaded file saved to: {temp_path}")

            progress.progress(10, text="正在处理问卷...")

            if process_full:
                from integrated_reporting_system import integrate_all_modules
                from group2_invalid_questionnaire_screening1 import (
                    normalize_dataframe, infer_columns, screen_questionnaires,
                    clean_valid_data, ScreeningConfig
                )

                raw_df, read_info = None, None
                if uploaded_file.name.endswith('.csv'):
                    try:
                        raw_df = pd.read_csv(temp_path, encoding='utf-8-sig')
                    except:
                        raw_df = pd.read_csv(temp_path, encoding='gbk')
                else:
                    # 尝试读取Excel文件
                    try:
                        if uploaded_file.name.lower().endswith('.xls'):
                            # .xls格式尝试使用xlrd引擎
                            raw_df = pd.read_excel(temp_path, engine='xlrd')
                        else:
                            # .xlsx格式使用openpyxl引擎
                            raw_df = pd.read_excel(temp_path, engine='openpyxl')
                    except ImportError:
                        st.error("读取.xls文件需要安装xlrd模块，请先安装：pip install xlrd")
                        raise
                    except Exception as e:
                        st.error(f"读取Excel文件失败: {str(e)}")
                        raise

                standard_df = normalize_dataframe(raw_df)
                column_info = infer_columns(standard_df)

                config = ScreeningConfig()
                valid_df, invalid_df, log_df, screening_result, context = screen_questionnaires(
                    standard_df, config=config, column_info=column_info
                )
                cleaned_df, cleaning_report = clean_valid_data(
                    valid_df=valid_df,
                    duration_col=context.get("duration_column"),
                )

                progress.progress(50, text="正在生成图表...")

                chart_config = ChartConfig(
                    width=chart_width,
                    height=chart_width * 0.6,
                    dpi=chart_dpi,
                    color_scheme=color_scheme,
                )

                analyzer = ComprehensiveAnalyzer(
                    data=cleaned_df,
                    column_info=column_info,
                    config=chart_config,
                    chart_output_dir=str(CHARTS_DIR)
                )

                single_results, multi_results, likert_results = analyzer.analyze_all_questions()

                from integrated_reporting_system import ComprehensiveReport
                report = ComprehensiveReport(
                    report_title="问卷综合分析报告",
                    generated_at=pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
                    data_source=uploaded_file.name,
                    total_respondents=len(standard_df),
                    valid_respondents=len(cleaned_df),
                    response_rate=len(cleaned_df) / len(standard_df) if len(standard_df) > 0 else 0,
                    single_choice_results=single_results,
                    multiple_choice_results=multi_results,
                    likert_scale_results=likert_results,
                    overall_analysis="",
                    chart_output_dir=str(CHARTS_DIR),
                )

                st.session_state["comprehensive_report"] = report
                st.session_state["chart_output_dir"] = str(CHARTS_DIR)

                progress.progress(70, text="正在保存图表...")
                exporter = ReportExporter(report, output_dir=output_dir)
                export_results = exporter.export_all_formats()
                st.session_state["export_results"] = export_results

                progress.progress(100, text="处理完成")
                st.success("完整处理完成！")

                st.session_state["questionnaire_result"] = {
                    "standard_data": standard_df,
                    "cleaned_data": cleaned_df,
                    "column_info": column_info,
                    "screening_result": screening_result,
                }

            else:
                result = process_questionnaire(temp_path, output_dir=output_dir)
                st.session_state["questionnaire_result"] = result
                progress.progress(100, text="处理完成")
                st.success("基础处理完成！")

        except Exception as exc:
            st.error("处理失败")
            import traceback
            st.code(traceback.format_exc())


if export_reports and st.session_state.get("comprehensive_report"):
    try:
        report = st.session_state["comprehensive_report"]
        exporter = ReportExporter(report, output_dir=output_dir)

        export_results = {}

        if export_markdown:
            md_path = exporter.export_to_markdown()
            export_results["markdown"] = md_path
            st.success(f"✅ Markdown报告已导出: `{md_path}`")

        if export_json:
            json_path = exporter.export_to_json()
            export_results["json"] = json_path
            st.success(f"✅ JSON报告已导出: `{json_path}`")

        if export_csv:
            csv_path = exporter.export_to_csv()
            export_results["csv"] = csv_path
            st.success(f"✅ CSV统计表已导出: `{csv_path}`")

        if export_excel:
            excel_path = exporter.export_combined_excel()
            export_results["excel"] = excel_path
            st.success(f"✅ Excel综合报告已导出: `{excel_path}`")

        st.session_state["export_results"] = export_results

    except Exception as exc:
        st.error("报告导出失败")
        import traceback
        st.code(traceback.format_exc())


if st.session_state.get("questionnaire_result"):
    result = st.session_state["questionnaire_result"]
    col1, col2, col3, col4 = st.columns(4)

    if "screening_result" in result:
        summary = result["screening_result"]
        col1.metric("原始问卷", getattr(summary, 'total_rows', 'N/A'))
        col2.metric("有效问卷", getattr(summary, 'valid_rows', 'N/A'))
        col3.metric("无效问卷", getattr(summary, 'invalid_rows', 'N/A'))
        col4.metric("有效率", f"{getattr(summary, 'valid_rate', 0):.1%}")
    else:
        std_data = result.get("standard_data", pd.DataFrame())
        col1.metric("数据行数", std_data.shape[0])
        col2.metric("数据列数", std_data.shape[1])
        col3.metric("题目数", len(result.get("column_info", {}).get("answer_columns", [])))
        col4.metric("状态", "已处理")

    st.divider()

    tab1, tab2, tab3, tab4 = st.tabs(["📋 数据预览", "📊 图表展示", "📝 分析报告", "📥 文件下载"])

    with tab1:
        st.subheader("标准化数据预览")
        if "cleaned_data" in result:
            st.dataframe(result["cleaned_data"].head(50), use_container_width=True, height=400)
        elif "standard_data" in result:
            st.dataframe(result["standard_data"].head(50), use_container_width=True, height=400)

        if "filter_log" in result:
            st.subheader("筛查日志预览")
            st.dataframe(result["filter_log"].head(30), use_container_width=True, height=300)

    with tab2:
        st.subheader("📈 生成图表展示")

        if st.session_state.get("comprehensive_report"):
            report = st.session_state["comprehensive_report"]

            if report.single_choice_results:
                st.markdown("### 单选题图表")
                cols = st.columns(2)
                for i, r in enumerate(report.single_choice_results[:6]):
                    if r.chart_path and Path(r.chart_path).exists():
                        with cols[i % 2]:
                            st.image(r.chart_path, caption=f"{r.question_id}: {r.question_name}", use_container_width=True)
                    if i >= 5:
                        st.info(f"还有 {len(report.single_choice_results) - 6} 道单选题未展示")
                        break

            if report.multiple_choice_results:
                st.markdown("### 多选题图表")
                cols = st.columns(2)
                for i, r in enumerate(report.multiple_choice_results[:4]):
                    if r.chart_path and Path(r.chart_path).exists():
                        with cols[i % 2]:
                            st.image(r.chart_path, caption=f"{r.question_id}: {r.question_name}", use_container_width=True)
                    if i >= 3:
                        st.info(f"还有 {len(report.multiple_choice_results) - 4} 道多选题未展示")
                        break

            if report.likert_scale_results:
                st.markdown("### 量表题图表")
                cols = st.columns(2)
                for i, r in enumerate(report.likert_scale_results[:4]):
                    if r.chart_path and Path(r.chart_path).exists():
                        with cols[i % 2]:
                            st.image(r.chart_path, caption=r.question_name, use_container_width=True)
                    if i >= 3:
                        st.info(f"还有 {len(report.likert_scale_results) - 4} 道量表题未展示")
                        break
        else:
            st.info("请先点击「完整处理」生成图表")

    with tab3:
        st.subheader("📝 分析报告")

        if st.session_state.get("comprehensive_report"):
            report = st.session_state["comprehensive_report"]

            col_sum1, col_sum2, col_sum3 = st.columns(3)
            col_sum1.metric("单选题", len(report.single_choice_results))
            col_sum2.metric("多选题", len(report.multiple_choice_results))
            col_sum3.metric("量表题", len(report.likert_scale_results))

            if report.single_choice_results:
                st.markdown("#### 单选题分析")
                for r in report.single_choice_results[:5]:
                    with st.expander(f"{r.question_id}: {r.question_name}"):
                        st.markdown(f"**有效回答**: {r.valid_responses} | **缺失**: {r.missing_count}（{r.missing_rate:.1%}）")
                        st.markdown(f"**分析**: {r.analysis_text}")

            if report.multiple_choice_results:
                st.markdown("#### 多选题分析")
                for r in report.multiple_choice_results[:5]:
                    with st.expander(f"{r.question_id}: {r.question_name}"):
                        st.markdown(f"**有效回答**: {r.valid_responses} | **总选择**: {sum(r.frequency_table.values())}")
                        st.markdown(f"**分析**: {r.analysis_text}")

            if report.likert_scale_results:
                st.markdown("#### 量表题分析")
                for r in report.likert_scale_results[:5]:
                    mean_val = r.central_tendency.get('mean', 0) if r.central_tendency else 0
                    std_val = r.dispersion.get('std', 0) if r.dispersion else 0
                    with st.expander(r.question_name):
                        st.markdown(f"**均值**: {mean_val:.3f} | **标准差**: {std_val:.3f}")
                        st.markdown(f"**分析**: {r.analysis_text}")
        else:
            st.info("请先点击「完整处理」生成分析报告")

    with tab4:
        st.subheader("📥 导出文件")

        if st.session_state.get("export_results"):
            for fmt, path in st.session_state["export_results"].items():
                if path and Path(path).exists():
                    with open(path, "rb") as f:
                        data = f.read()
                    file_name = Path(path).name
                    st.download_button(
                        label=f"下载 {file_name}",
                        data=data,
                        file_name=file_name,
                        mime="application/octet-stream",
                    )
        else:
            st.info("请先完成报告导出")

        st.markdown("---")
        st.markdown("**AI智能分析（可选）**")
        st.caption("不填API Key也能完成前面的数据处理；这里只是额外生成AI文字分析")

        if st.button("🤖 生成AI分析报告", type="secondary"):
            try:
                if not api_key or not base_url or not model:
                    st.warning("请在侧边栏填写完整的API配置")
                else:
                    with st.spinner("正在调用AI分析..."):
                        report = st.session_state.get("comprehensive_report") or build_survey_report(
                            result.get("standard_data", pd.DataFrame()),
                            result.get("column_info", {}),
                            screening_result=result.get("screening_result"),
                        )
                        content, raw = generate_ai_analysis(
                            report=report,
                            api_key=api_key,
                            base_url=base_url,
                            model=model,
                            provider_name=provider_name,
                            user_requirement=user_requirement,
                        )

                        ai_dir = Path(output_dir)
                        ai_dir.mkdir(parents=True, exist_ok=True)
                        ai_report_path = ai_dir / "ai_generated_report.md"
                        ai_raw_path = ai_dir / "ai_response_raw.json"

                        ai_report_path.write_text(content, encoding="utf-8")
                        ai_raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")

                        st.success("AI分析完成！")
                        st.markdown(content)
                        st.info(f"文件已保存至: `{ai_dir}`")
            except Exception as exc:
                st.error("AI分析失败")
                import traceback
                st.code(traceback.format_exc())

elif not uploaded_file:
    st.info("👆 请上传Excel或CSV格式的问卷数据文件开始分析")

    with st.expander("ℹ️ 使用说明"):
        st.markdown("""
        ## 问卷数据一体化处理平台 使用指南

        ### 1. 样本量测算
        - 设置置信度、允许误差等参数
        - 系统自动计算理论最小样本量
        - 建议发放量考虑了30%无效问卷缓冲

        ### 2. 数据处理
        - **基础处理**: 仅进行无效问卷筛查
        - **完整处理**: 筛查 + 批量生成图表 + 标准化文案

        ### 3. 图表类型
        - 单选题: 饼图 + 柱状图
        - 多选题: 水平柱状图
        - 量表题: 直方图 + 分布图

        ### 4. 报告导出
        - Markdown: 可直接用于报告撰写
        - JSON: 程序化调用
        - CSV: 数据再分析
        - Excel: 综合报告（含多Sheet）

        ### 5. AI分析
        - 填写侧边栏API配置
        - 自动生成统计报告文字解读
        """)

        st.markdown("""
        ## 数据格式要求

        ### 输入文件
        - 问卷星导出的Excel (.xlsx, .xls, .xlsm)
        - CSV格式 (utf-8-sig或gbk编码)

        ### 自动识别
        - **单选题**: 选项数量≤8，数值型
        - **多选题**: 含分隔符（,、；、、）的文本
        - **量表题**: 1-5或1-7数值范围

        ### 元信息列（自动排除）
        - 答卷编号、提交时间、所用时间
        - 来源IP、地域、设备信息
        - 姓名、学号等个人信息
        """)

else:
    st.info("👆 点击上方按钮开始处理问卷数据")
