# -*- coding: utf-8 -*-
"""
问卷数据一体化处理平台 - 整合版
整合所有模块：数据接入、无效筛查、图表生成、报告导出
"""

from __future__ import annotations

import io
import json
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import numpy as np
import pandas as pd
import streamlit as st

# 动态获取工作目录，确保跨平台兼容
WORKSPACE_DIR = Path(__file__).resolve().parent
TEMP_DIR = WORKSPACE_DIR / "temp_uploads"
OUTPUT_DIR = WORKSPACE_DIR / "integrated_output"
CHARTS_DIR = OUTPUT_DIR / "charts"

# 确保所有目录存在
for dir_path in [WORKSPACE_DIR, TEMP_DIR, OUTPUT_DIR, CHARTS_DIR]:
    try:
        dir_path.mkdir(parents=True, exist_ok=True)
        print(f"[INFO] Created/verified directory: {dir_path}")
    except Exception as e:
        print(f"[WARNING] Could not create directory {dir_path}: {e}")

# 添加工作目录到路径
if str(WORKSPACE_DIR) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_DIR))

print(f"[DEBUG] Platform: {sys.platform}")
print(f"[DEBUG] File path: {__file__}")
print(f"[DEBUG] WORKSPACE_DIR: {WORKSPACE_DIR}")
print(f"[DEBUG] TEMP_DIR: {TEMP_DIR}")
print(f"[DEBUG] OUTPUT_DIR: {OUTPUT_DIR}")

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
    ComprehensiveReport,
    ReportExporter,
)

# 页面配置
st.set_page_config(
    page_title="问卷数据一体化处理平台",
    page_icon="📊",
    layout="wide",
)

st.title("📊 问卷数据一体化处理平台")

# 侧边栏配置
with st.sidebar:
    st.subheader("⚙️ AI 接口配置（可选）")
    ai_provider = st.selectbox("服务商", list(AI_PROVIDER_PRESETS.keys()))
    api_key = st.text_input("API Key", type="password")
    base_url = st.text_input("Base URL", value=AI_PROVIDER_PRESETS[ai_provider]["base_url"])
    model_name = st.text_input("模型名", value=AI_PROVIDER_PRESETS[ai_provider].get("model", ""))
    ai_prompt = st.text_area("补充要求", value="例如：按课程论文风格生成...", height=100)

    st.divider()
    st.subheader("🎨 图表配置")
    color_scheme = st.selectbox("配色方案", ["professional", "default", "bright", "pastel"])
    dpi = st.slider("图表分辨率", 100, 300, 150)
    chart_width = st.slider("图表宽度(英寸)", 8, 16, 12)

# 样本量计算
st.subheader("📈 样本量测算")
col1, col2, col3 = st.columns(3)
with col1:
    confidence = st.number_input("置信度(%)", 90, 99, 95, 1)
with col2:
    margin = st.number_input("允许误差(%)", 1, 10, 5, 1)
with col3:
    population = st.number_input("总体规模", 100, 1000000, 10000)

if st.button("🔢 计算样本量"):
    try:
        result = calculate_sample(
            confidence_level=confidence / 100,
            margin_of_error=margin / 100,
            population=population,
        )
        st.success(f"理论最小样本量：**{result['min_sample']}** 份")
        st.info(f"含30%无效缓冲的建议发放量：**{result['suggested_sample']}** 份")
        if result.get("fpc_applied"):
            st.warning("已应用有限总体校正（FPC）")
    except Exception as e:
        st.error(f"计算失败：{e}")

# 问卷数据处理
st.divider()
st.subheader("📁 问卷数据处理")

uploaded_file = st.file_uploader(
    "选择 Excel / CSV 文件",
    type=["xlsx", "xls", "xlsm", "csv"],
    help="支持问卷星导出的Excel和CSV格式"
)

output_dir_input = st.text_input("输出目录", value=str(OUTPUT_DIR))
Path(output_dir_input).mkdir(parents=True, exist_ok=True)

col_btn1, col_btn2, col_btn3 = st.columns(3)

with col_btn1:
    process_basic = st.button("🔍 基础处理（筛查）", type="primary", use_container_width=True)

with col_btn2:
    process_full = st.button("📊 完整处理（筛查+图表）", type="primary", use_container_width=True)

with col_btn3:
    export_report = st.button("📥 导出报告", type="primary", use_container_width=True)

if process_basic or process_full:
    if uploaded_file is None:
        st.warning("请先上传文件")
    else:
        try:
            progress = st.progress(0, text="保存上传文件...")
            
            # 保存上传的文件到临时目录
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
                    raw_df = pd.read_excel(temp_path)
                
                progress.progress(20, text="数据标准化...")
                norm_df = normalize_dataframe(raw_df)
                
                progress.progress(30, text="字段识别...")
                column_info = infer_columns(norm_df)
                
                progress.progress(40, text="无效问卷筛查...")
                screening_config = ScreeningConfig()
                valid_df, invalid_df, screening_log = screen_questionnaires(norm_df, column_info, screening_config)
                
                progress.progress(50, text="数据清洗...")
                clean_df = clean_valid_data(valid_df, column_info)
                
                progress.progress(60, text="分析问卷...")
                analyzer = ComprehensiveAnalyzer(
                    data=clean_df,
                    column_info=column_info,
                    config=None,
                    chart_output_dir=str(CHARTS_DIR)
                )
                single_results, multi_results, likert_results = analyzer.analyze_all_questions()
                
                progress.progress(70, text="生成报告...")
                report = analyzer.generate_report()
                
                progress.progress(80, text="导出报告...")
                exporter = ReportExporter(report, output_dir=output_dir_input)
                md_path = exporter.export_to_markdown()
                json_path = exporter.export_to_json()
                csv_path = exporter.export_to_csv()
                excel_path = exporter.export_combined_excel()
                
                progress.progress(100, text="处理完成!")
                
                st.success(f"✅ 处理完成！报告已保存到 {output_dir_input}")
                st.session_state["comprehensive_report"] = report
                
                with st.expander("📋 处理结果摘要"):
                    st.write(f"总问卷数: {len(raw_df)}")
                    st.write(f"有效问卷数: {len(valid_df)}")
                    st.write(f"无效问卷数: {len(invalid_df)}")
                    st.write(f"有效率: {(len(valid_df)/len(raw_df)*100):.1f}%")
            
            else:
                # 基础处理 - 仅筛查
                result = process_questionnaire(str(temp_path), output_dir=output_dir_input)
                progress.progress(100, text="处理完成!")
                
                if result.get("success"):
                    st.success(f"✅ 基础处理完成！结果已保存到 {output_dir_input}")
                    st.write(f"总问卷数: {result.get('total_count', 0)}")
                    st.write(f"有效问卷数: {result.get('valid_count', 0)}")
                    st.write(f"无效问卷数: {result.get('invalid_count', 0)}")
                else:
                    st.error(f"处理失败: {result.get('error', '未知错误')}")
        
        except Exception as e:
            st.error(f"处理失败: {e}")
            import traceback
            st.exception(traceback.format_exc())

# 结果展示
if "comprehensive_report" in st.session_state:
    report = st.session_state["comprehensive_report"]
    
    tab1, tab2, tab3, tab4 = st.tabs(["📊 图表", "📝 报告", "📈 统计", "📥 导出"])
    
    with tab1:
        st.subheader("图表展示")
        if report.single_choice_results:
            st.markdown("### 单选题图表")
            cols = st.columns(2)
            for i, r in enumerate(report.single_choice_results[:4]):
                if r.chart_path and Path(r.chart_path).exists():
                    with cols[i % 2]:
                        st.image(r.chart_path, caption=r.question_name, use_container_width=True)
        
        if report.likert_scale_results:
            st.markdown("### 量表题图表")
            cols = st.columns(2)
            for i, r in enumerate(report.likert_scale_results[:4]):
                if r.chart_path and Path(r.chart_path).exists():
                    with cols[i % 2]:
                        st.image(r.chart_path, caption=r.question_name, use_container_width=True)
    
    with tab2:
        st.subheader("分析报告")
        if report.single_choice_results:
            for r in report.single_choice_results[:5]:
                with st.expander(f"{r.question_id}: {r.question_name}"):
                    st.markdown(r.analysis_text)
        
        if report.likert_scale_results:
            st.markdown("#### 量表题分析")
            for r in report.likert_scale_results[:5]:
                mean_val = r.central_tendency.get('mean', 0) if r.central_tendency else 0
                std_val = r.dispersion.get('std', 0) if r.dispersion else 0
                with st.expander(r.question_name):
                    st.markdown(f"**均值**: {mean_val:.3f} | **标准差**: {std_val:.3f}")
                    st.markdown(f"**分析**: {r.analysis_text}")
    
    with tab3:
        st.subheader("统计摘要")
        col_sum1, col_sum2, col_sum3 = st.columns(3)
        with col_sum1:
            st.metric("总问卷数", report.total_respondents)
        with col_sum2:
            st.metric("有效问卷数", report.valid_respondents)
        with col_sum3:
            st.metric("有效率", f"{report.response_rate:.1%}")
    
    with tab4:
        st.subheader("导出文件")
        if Path(output_dir_input).exists():
            files = list(Path(output_dir_input).glob("*.*"))
            for f in files:
                st.write(f"- {f.name}")
