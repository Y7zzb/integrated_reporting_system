import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO

# 信度计算
def cronbach_alpha(item_df):
    item_df = item_df.dropna(axis=0, how="any")
    k = item_df.shape[1]
    if k <= 1:
        return np.nan
    corr_matrix = item_df.corr().values.copy()
    np.fill_diagonal(corr_matrix, np.nan)
    avg_corr = np.nanmean(corr_matrix)
    alpha = (k * avg_corr) / (1 + (k - 1) * avg_corr)
    return round(alpha, 3)

def alpha_per_item_deleted(work_data):
    total_alpha = cronbach_alpha(work_data)
    del_alpha_list = []
    for col in work_data.columns:
        temp_data = work_data.drop(columns=[col])
        del_alpha_list.append(cronbach_alpha(temp_data) if temp_data.shape[1] >= 2 else total_alpha)
    return total_alpha, del_alpha_list

# 页面配置
st.set_page_config(page_title="李克特量表全套统计+信度检验", layout="wide")
st.title("📊 李克特量表全套统计+信度检验")

# 上传文件
uploaded_file = st.file_uploader("📁 上传Excel量表文件", type=["xlsx","xls"])

if uploaded_file:
    df_original = pd.read_excel(uploaded_file)
    st.success("✅ 文件读取成功")

    # 保留原始数据预览
    st.dataframe(df_original, use_container_width=True, height=280)

    # 预处理
    df_process = df_original.copy()
    scale_df = df_process.select_dtypes(include=[np.number])

    # 剔除纯编号列
    for col in scale_df.columns:
        s_sorted = scale_df[col].dropna().sort_values().reset_index(drop=True)
        if list(s_sorted) == list(range(1, len(s_sorted)+1)):
            scale_df = scale_df.drop(columns=[col])

    if scale_df.empty:
        st.warning("⚠️ 未识别到有效量表题项")
        st.stop()

    # 自动生成Q编号映射
    col_to_q = {col:f"Q{i+1}" for i, col in enumerate(scale_df.columns)}
    q_to_col = {v:k for k,v in col_to_q.items()}

    # 配置区
    st.divider()
    st.subheader("⚙️ 自定义配置")

    # 维度输入框改为【空白】，无默认内容
    dimension_input = st.text_area(
        "维度分组设置（格式：维度名称=Q1,Q2...）",
        height=150,
        value=""
    )

    auto_rev_check = st.checkbox("✅ 开启自动反向题识别", value=True)
    manual_rev_select = st.multiselect("手动补充/修正反向题", scale_df.columns.tolist())
    group_column = st.selectbox("分组对比列（性别/组别）", ["无分组"] + df_original.columns.tolist())

    # 一键分析
    if st.button("🚀 一键启动全套专业分析", type="primary"):
        work_df = scale_df.copy()
        reverse_items = []

        # 反向题处理
        if auto_rev_check:
            mean_sort = work_df.mean().sort_values()
            detect_cnt = max(1, int(len(mean_sort)*0.2))
            auto_rev = list(mean_sort.iloc[:detect_cnt].index)
            reverse_items.extend(auto_rev)
            st.info(f"🤖 系统自动识别反向题：{', '.join(auto_rev)}")

        reverse_items = list(set(reverse_items + manual_rev_select))
        for c in reverse_items:
            work_df[c] = 6 - work_df[c]

        # 1. 题项统计表：Q编号 + 纯题干（去除编号）
        st.subheader("📋 题项完整统计详情")
        total_alpha, item_del_alpha = alpha_per_item_deleted(work_df)

        def clean_title(s):
            # 去除开头 Q+数字+空格
            import re
            return re.sub(r"^Q\d+\s*", "", s)

        item_stat_df = pd.DataFrame({
            "题项编号": [col_to_q[c] for c in work_df.columns],
            "原题名称": [clean_title(c) for c in work_df.columns],
            "平均分": work_df.mean().round(3),
            "标准差": work_df.std().round(3),
            "方差": work_df.var().round(3),
            "最小值": work_df.min(),
            "最大值": work_df.max(),
            "极差": (work_df.max() - work_df.min()).round(3),
            "下四分位数Q1": work_df.quantile(0.25).round(3),
            "中位数Q2": work_df.quantile(0.5).round(3),
            "上四分位数Q3": work_df.quantile(0.75).round(3),
            "删除本题后整体α系数": item_del_alpha
        })
        st.dataframe(item_stat_df, use_container_width=True)

        # 2. 整体信度
        st.subheader("🔐 整体量表克隆巴赫α信度")
        if total_alpha >=0.9:
            note = "🌟 信度极佳"
        elif total_alpha >=0.8:
            note = "✅ 信度良好，完全符合学术发表标准"
        elif total_alpha >=0.7:
            note = "⚠️ 信度可接受"
        else:
            note = "❌ 信度偏低，建议优化题项"
        st.info(f"整体量表α系数 = {total_alpha}\n{note}")

        # 3. 维度统计
        st.subheader("🧩 维度综合统计 & 维度信度")
        dim_stat_list = []
        dim_df = pd.DataFrame()

        for line in dimension_input.strip().splitlines():
            if "=" not in line:
                continue
            dim_name, cols_str = line.split("=",1)
            dim_name = dim_name.strip()
            q_list = [c.strip() for c in cols_str.replace("，",",").split(",")]

            # 精准匹配Q编号
            valid_cols = [q_to_col[q] for q in q_list if q in q_to_col]
            if not valid_cols:
                continue

            sub_df = work_df[valid_cols]
            dim_score = sub_df.mean(axis=1)
            dim_df[dim_name] = dim_score

            dim_stat_list.append({
                "维度名称": dim_name,
                "平均分": round(dim_score.mean(),3),
                "标准差": round(dim_score.std(),3),
                "方差": round(dim_score.var(),3),
                "最小值": round(dim_score.min(),3),
                "最大值": round(dim_score.max(),3),
                "极差": round(dim_score.max()-dim_score.min(),3),
                "下四分位数Q1": round(dim_score.quantile(0.25),3),
                "上四分位数Q3": round(dim_score.quantile(0.75),3),
                "维度α系数": cronbach_alpha(sub_df)
            })

        # 渲染维度表格
        if dim_stat_list:
            dim_full_stat = pd.DataFrame(dim_stat_list)
            st.dataframe(dim_full_stat, use_container_width=True)
        else:
            st.info("请在上方填写维度分组后再查看数据")

        # 4. 分组对比
        if group_column != "无分组":
            st.subheader("🆚 组别横向差异对比")
            group_merge = pd.concat([work_df, df_original[group_column]], axis=1)
            group_avg = group_merge.groupby(group_column).mean(numeric_only=True).round(2)
            st.dataframe(group_avg, use_container_width=True)
            st.bar_chart(group_avg.T, height=520, use_container_width=True)

        # 5. Excel导出
        st.subheader("📥 一键下载全套Excel分析报告")
        final_export = pd.concat([df_original, work_df, dim_df], axis=1)
        output_buffer = BytesIO()

        with pd.ExcelWriter(output_buffer, engine="openpyxl") as w:
            final_export.to_excel(w, index=False, sheet_name="原始+计分完整数据")
            item_stat_df.to_excel(w, index=False, sheet_name="题项全套统计")
            if dim_stat_list:
                dim_full_stat.to_excel(w, index=False, sheet_name="维度全套统计与信度")

        st.download_button(
            "📁 下载完整Excel报告",
            data=output_buffer.getvalue(),
            file_name="量表_全套统计信度报告.xlsx"
        )

else:
    st.info("👆 上传你的Excel量表文件，一键开始专业分析")