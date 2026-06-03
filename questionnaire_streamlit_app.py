from __future__ import annotations

import json
import sys
from pathlib import Path

import streamlit as st


WORKSPACE_DIR = Path(r"C:\Users\派大星\PyCharmMiscProject")
TEMP_DIR = Path(r"C:\Users\派大星\AppData\Local\Temp")
DESKTOP_DIR = Path(r"C:\Users\派大星\Desktop")

for p in (WORKSPACE_DIR, TEMP_DIR, DESKTOP_DIR):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from questionnaire_platform_core import (  # noqa: E402
    AI_PROVIDER_PRESETS,
    build_survey_report,
    generate_ai_analysis,
    process_questionnaire,
    save_report_outputs,
)


st.set_page_config(page_title="问卷数据一体化处理", layout="wide")
st.title("问卷数据一体化处理")
st.caption("一次完成数据接入、标准化、无效问卷筛查，以及可选的 API 文本分析")

with st.sidebar:
    st.subheader("AI 接口")
    provider_name = st.selectbox("服务商", list(AI_PROVIDER_PRESETS.keys()), index=0)
    provider_preset = AI_PROVIDER_PRESETS[provider_name]
    api_key = st.text_input("API Key", type="password")
    base_url = st.text_input("Base URL", value=provider_preset.get("base_url", ""))
    model = st.text_input("模型名", value=provider_preset.get("model", ""))
    user_requirement = st.text_area("补充要求", placeholder="例如：按课程论文风格生成，重点解释无效问卷特征")


st.divider()
st.subheader("📊 样本量测算")


col_c1, col_c2 = st.columns(2)
with col_c1:
    conf_input = st.selectbox("置信度", [0.90, 0.95, 0.99], index=1, help="通常选95%")
    margin_input = st.slider("允许误差 (%)", 1, 10, 5, help="调查允许的绝对误差范围")
    p_input = st.slider("预期比例 (p)", 0.1, 0.9, 0.5, help="不确定时选0.5（最保守）")
with col_c2:
    pop_input = st.number_input("总体数量（0=无限总体）", min_value=0, value=10000, step=1000)
    actual_input = st.number_input("实际有效样本数（从组员2获取）", min_value=0, value=320, step=10)

if st.button("开始测算样本量", type="primary"):
    try:
        from questionnaire_platform_core import calculate_sample

        res = calculate_sample(
            confidence=conf_input,
            margin_error=margin_input / 100.0,
            p=p_input,
            population=pop_input,
            actual_sample=actual_input,
        )
        st.success(f"✅ 理论最小样本量：**{res['min_sample']}** 份")
        st.info(f"📌 建议发放量：**{res['suggested']}** 份（考虑30%无效问卷）")
        if res['is_sufficient'] is True:
            st.success("🎉 实际样本达标，统计结果可靠")
        elif res['is_sufficient'] is False:
            st.warning(f"⚠️ 实际样本不足，还差 **{res['gap']}** 份，请继续收集问卷")
        else:
            st.info("💡 未输入实际样本数，请从组员2获取后填入")
    except Exception as e:
        st.error(f"计算失败：{e}")


st.caption("参数微调模拟（拖动下面滑块试试）")
sim_margin = st.slider("模拟调整允许误差 (%)", 1, 10, 5, key="sim_margin", help="观察样本量变化趋势")
if st.button("模拟运行", key="sim_btn"):
    try:
        from questionnaire_platform_core import calculate_sample

        sim_res = calculate_sample(
            confidence=conf_input,
            margin_error=sim_margin / 100.0,
            p=p_input,
            population=pop_input,
            actual_sample=actual_input,
        )
        st.info(f"当允许误差为 {sim_margin}% 时，理论最小样本量为 **{sim_res['min_sample']}** 份")
    except Exception as e:
        st.error(f"模拟失败：{e}")

uploaded_file = st.file_uploader(
    "选择 Excel / CSV 文件",
    type=["xlsx", "xls", "xlsm", "csv"],
)

default_output_dir = str(WORKSPACE_DIR / "output_group2_streamlit")
output_dir = st.text_input("输出目录", value=default_output_dir)

if uploaded_file is not None and st.button("开始处理", type="primary"):
    try:
        progress = st.progress(0, text="保存上传文件...")
        temp_path = WORKSPACE_DIR / uploaded_file.name
        temp_path.write_bytes(uploaded_file.getvalue())

        progress.progress(20, text="正在处理问卷...")
        result = process_questionnaire(temp_path, output_dir=output_dir)

        progress.progress(80, text="正在生成本地分析摘要...")
        report = build_survey_report(
            result["standard_data"],
            result["column_info"],
            screening_result=result["screening_result"],
        )
        report_outputs = save_report_outputs(report, output_dir)

        st.session_state["questionnaire_result"] = result
        st.session_state["questionnaire_report"] = report
        st.session_state["report_outputs"] = report_outputs
        st.session_state["output_dir"] = output_dir

        progress.progress(100, text="处理完成")
        st.success("问卷处理完成")
    except Exception as exc:
        st.error("处理失败")
        st.exception(exc)

result = st.session_state.get("questionnaire_result")
report = st.session_state.get("questionnaire_report")
report_outputs = st.session_state.get("report_outputs", {})
latest_output_dir = Path(st.session_state.get("output_dir", output_dir))

if result:
    adapter = result["data_adapter_report"]
    summary = result["screening_result"]
    profile = result["profile"]

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("原始行数", profile.rows)
    c2.metric("标准化列数", profile.columns)
    c3.metric("题目列数", profile.answer_columns)
    c4.metric("无效率", f"{summary.invalid_rate:.2%}")

    left, right = st.columns(2)
    with left:
        st.subheader("第一阶段：数据接入与标准化")
        st.write(f"文件: {adapter['read_info']['file_name']}")
        st.write(f"标准化后规模: {adapter['standard_data_shape'][0]} 行, {adapter['standard_data_shape'][1]} 列")
        st.write(f"元信息列数: {adapter['profile'].metadata_columns}")
        st.write(f"题目列数: {adapter['profile'].answer_columns}")
        st.dataframe(result["standard_data"].head(20), use_container_width=True)

    with right:
        st.subheader("第二阶段：无效问卷筛查")
        st.write(f"总问卷数: {summary.total_rows}")
        st.write(f"有效问卷数: {summary.valid_rows}")
        st.write(f"无效问卷数: {summary.invalid_rows}")
        st.write(f"有效率: {summary.valid_rate:.2%}")
        st.write(f"无效率: {summary.invalid_rate:.2%}")
        st.dataframe(result["filter_log"].head(20), use_container_width=True)

    st.subheader("输出文件")
    for name, path in result["output_paths"].items():
        st.write(f"{name}: `{path}`")
    for name, path in report_outputs.items():
        st.write(f"{name}: `{path}`")
    st.info(f"结果已导出到: {latest_output_dir.resolve()}")

    st.subheader("AI 分析")
    st.caption("不填 API Key 也能完成前面的数据处理；这里只是额外生成文字分析。")
    if st.button("生成 AI 分析"):
        try:
            if not report:
                raise ValueError("请先完成问卷处理")
            content, raw = generate_ai_analysis(
                report=report,
                api_key=api_key,
                base_url=base_url,
                model=model,
                provider_name=provider_name,
                user_requirement=user_requirement,
            )
            ai_report_path = latest_output_dir / "ai_generated_report.md"
            ai_raw_path = latest_output_dir / "ai_response_raw.json"
            ai_report_path.write_text(content, encoding="utf-8")
            ai_raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            st.session_state["ai_report"] = content
            st.success("AI 分析已生成")
            st.write(content)
            st.write(f"ai_generated_report.md: `{ai_report_path}`")
            st.write(f"ai_response_raw.json: `{ai_raw_path}`")
        except Exception as exc:
            st.error("AI 分析失败")
            st.exception(exc)

    if st.session_state.get("ai_report"):
        st.markdown(st.session_state["ai_report"])
else:
    st.info("请先上传文件并点击开始处理")
