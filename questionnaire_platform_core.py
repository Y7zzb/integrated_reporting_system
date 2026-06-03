from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd

try:
    from group2_invalid_questionnaire_screening import process_file as _process_questionnaire
except ModuleNotFoundError:
    from group2_invalid_questionnaire_screening1 import process_file as _process_questionnaire

from ai_client import build_report_messages, call_openai_compatible_chat


AI_PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "Qwen": {
        "base_url": "https://dashscope.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "VolcEngine": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "",
    },
    "OpenAI Compatible": {
        "base_url": "https://api.openai.com/v1",
        "model": "",
    },
    "Custom": {
        "base_url": "",
        "model": "",
    },
}


def process_questionnaire(file_path: str | Path, output_dir: str | Path = "output_group2", sheet_name: int | str = 0) -> Dict[str, object]:
    return _process_questionnaire(file_path, output_dir=output_dir, sheet_name=sheet_name)


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(v) for v in value]
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:
            pass
    return value


def build_survey_report(
    standard_data: pd.DataFrame,
    column_info: Dict[str, list],
    screening_result: Optional[object] = None,
) -> Dict[str, Any]:
    rows, cols = standard_data.shape
    missing_cells = int(standard_data.isna().sum().sum())
    missing_ratio = round(missing_cells / (rows * cols), 4) if rows and cols else 0.0
    duplicated_rows = int(standard_data.duplicated().sum())
    report = {
        "generated_at": pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S"),
        "summary": {
            "rows": int(rows),
            "columns": int(cols),
            "metadata_columns": int(len(column_info.get("metadata_columns", []))),
            "answer_columns": int(len(column_info.get("answer_columns", []))),
            "missing_cells": missing_cells,
            "missing_ratio": missing_ratio,
            "duplicated_rows": duplicated_rows,
        },
        "column_info": {
            "metadata_columns": list(column_info.get("metadata_columns", [])),
            "answer_columns": list(column_info.get("answer_columns", [])),
        },
        "sample_columns": list(standard_data.columns[:20]),
    }
    if screening_result is not None:
        report["screening_result"] = _jsonable(screening_result)
    return report


def build_ai_context(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    column_info = report.get("column_info", {})
    screening = report.get("screening_result", {})
    lines = [
        "问卷数据分析摘要",
        f"行数: {summary.get('rows', 0)}",
        f"列数: {summary.get('columns', 0)}",
        f"元信息列数: {summary.get('metadata_columns', 0)}",
        f"题目列数: {summary.get('answer_columns', 0)}",
        f"缺失单元格数: {summary.get('missing_cells', 0)}",
        f"缺失率: {summary.get('missing_ratio', 0)}",
        f"重复行数: {summary.get('duplicated_rows', 0)}",
        "",
        "元信息列示例:",
        ", ".join(column_info.get("metadata_columns", [])[:10]) or "无",
        "",
        "题目列示例:",
        ", ".join(column_info.get("answer_columns", [])[:20]) or "无",
    ]
    if screening:
        lines.extend(
            [
                "",
                "无效筛查结果:",
                f"总问卷数: {screening.get('total_rows', 0)}",
                f"有效问卷数: {screening.get('valid_rows', 0)}",
                f"无效问卷数: {screening.get('invalid_rows', 0)}",
                f"有效率: {screening.get('valid_rate', 0)}",
                f"无效率: {screening.get('invalid_rate', 0)}",
                f"作答时长阈值(秒): {screening.get('duration_threshold_seconds', 0)}",
                f"缺答阈值: {screening.get('missing_threshold', 0)}",
            ]
        )
        breakdown = screening.get("reason_breakdown", {})
        if breakdown:
            lines.append("")
            lines.append("剔除原因统计:")
            for reason, count in sorted(breakdown.items(), key=lambda item: item[1], reverse=True):
                lines.append(f"- {reason}: {count}")
    return "\n".join(lines)


def generate_local_text_report(report: Dict[str, Any]) -> str:
    summary = report.get("summary", {})
    screening = report.get("screening_result", {})
    lines = [
        "# 问卷分析报告",
        "",
        "## 数据概况",
        f"- 行数: {summary.get('rows', 0)}",
        f"- 列数: {summary.get('columns', 0)}",
        f"- 元信息列: {summary.get('metadata_columns', 0)}",
        f"- 题目列: {summary.get('answer_columns', 0)}",
        f"- 缺失率: {summary.get('missing_ratio', 0)}",
        f"- 重复行数: {summary.get('duplicated_rows', 0)}",
    ]
    if screening:
        lines.extend(
            [
                "",
                "## 无效筛查",
                f"- 总问卷数: {screening.get('total_rows', 0)}",
                f"- 有效问卷数: {screening.get('valid_rows', 0)}",
                f"- 无效问卷数: {screening.get('invalid_rows', 0)}",
                f"- 有效率: {screening.get('valid_rate', 0)}",
                f"- 无效率: {screening.get('invalid_rate', 0)}",
                f"- 作答时长阈值(秒): {screening.get('duration_threshold_seconds', 0)}",
            ]
        )
        breakdown = screening.get("reason_breakdown", {})
        if breakdown:
            lines.append("")
            lines.append("### 剔除原因")
            for reason, count in sorted(breakdown.items(), key=lambda item: item[1], reverse=True):
                lines.append(f"- {reason}: {count}")
    return "\n".join(lines)


def save_report_outputs(report: Dict[str, Any], output_dir: str | Path) -> Dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    context = build_ai_context(report)
    local_report = generate_local_text_report(report)

    report_path = out / "survey_report.json"
    context_path = out / "ai_analysis_context.txt"
    markdown_path = out / "local_text_report.md"

    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(_jsonable(report), f, ensure_ascii=False, indent=2)
    context_path.write_text(context, encoding="utf-8")
    markdown_path.write_text(local_report, encoding="utf-8")

    return {
        "survey_report.json": report_path,
        "ai_analysis_context.txt": context_path,
        "local_text_report.md": markdown_path,
    }


def generate_ai_analysis(
    report: Dict[str, Any],
    api_key: str,
    base_url: str,
    model: str,
    provider_name: str = "Custom",
    user_requirement: str = "",
    temperature: float = 0.25,
    max_tokens: int = 1600,
    timeout: int = 120,
) -> Tuple[str, dict]:
    preset = AI_PROVIDER_PRESETS.get(provider_name, {})
    base_url = (base_url or preset.get("base_url", "")).strip()
    model = (model or preset.get("model", "")).strip()
    if not base_url:
        raise ValueError("Base URL 不能为空")
    if not api_key.strip():
        raise ValueError("API Key 不能为空")
    if not model:
        raise ValueError("模型名不能为空")

    context = build_ai_context(report)
    messages = build_report_messages(context, user_requirement=user_requirement)
    return call_openai_compatible_chat(
        base_url=base_url,
        api_key=api_key.strip(),
        model=model,
        messages=messages,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout,
    )

import math

def calculate_sample(
    confidence: float = 0.95,
    margin_error: float = 0.05,
    p: float = 0.5,
    population: int = 10000,
    actual_sample: int = 0,
) -> dict:
    """
    样本量计算函数（支持有限总体校正）
    返回字典包含 min_sample, suggested, is_sufficient, gap
    """

    if not (0 < confidence < 1):
        raise ValueError("置信度必须在0~1之间")
    if margin_error <= 0 or margin_error >= 1:
        raise ValueError("允许误差必须在0~1之间")
    if not (0 < p < 1):
        raise ValueError("预期比例必须在0~1之间")
    if population < 0:
        raise ValueError("总体数量不能为负数")
    if actual_sample < 0:
        raise ValueError("实际样本数不能为负数")


    z_dict = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
    z = z_dict.get(confidence, 1.96)


    n0 = (z**2 * p * (1 - p)) / (margin_error**2)
    min_sample = math.ceil(n0)


    if population > 0 and min_sample > 0.05 * population:
        min_sample = math.ceil(min_sample / (1 + (min_sample - 1) / population))

    suggested = math.ceil(min_sample * 1.3)

    is_sufficient = None
    gap = 0
    if actual_sample > 0:
        is_sufficient = (actual_sample >= min_sample)
        gap = min_sample - actual_sample if not is_sufficient else 0

    return {
        "min_sample": min_sample,
        "suggested": suggested,
        "actual_sample": actual_sample if actual_sample > 0 else None,
        "is_sufficient": is_sufficient,
        "gap": gap,
    }