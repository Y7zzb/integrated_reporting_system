from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd


SUPPORTED_EXTENSIONS = {".csv", ".xlsx", ".xls", ".xlsm"}
CSV_ENCODINGS = ("utf-8-sig", "utf-8", "gbk", "gb18030")

META_KEYWORDS = (
    "答卷编号",
    "答题编号",
    "序号",
    "id",
    "ID",
    "提交答卷时间",
    "提交时间",
    "开始时间",
    "结束时间",
    "所用时间",
    "作答时长",
    "答题时长",
    "填写时长",
    "用时",
    "耗时",
    "来源",
    "IP",
    "ip",
    "省份",
    "城市",
    "地区",
    "设备",
    "浏览器",
    "操作系统",
    "微信",
    "昵称",
    "姓名",
    "手机号",
    "电话",
    "邮箱",
    "学号",
    "班级",
)


@dataclass
class ScreeningConfig:
    min_duration_seconds: int = 45
    seconds_per_answer: float = 2.0
    missing_threshold: float = 0.40
    uniform_ratio_threshold: float = 0.90
    minimum_answered_for_uniform: int = 4
    nonsense_ratio_threshold: float = 0.60
    min_text_answers_for_nonsense: int = 2
    save_raw_snapshot: bool = True


@dataclass
class ScreeningResult:
    total_rows: int
    valid_rows: int
    invalid_rows: int
    valid_rate: float
    invalid_rate: float
    non_sampling_error_rate: float
    nonresponse_error_rate: float
    duration_threshold_seconds: float
    missing_threshold: float
    reason_breakdown: Dict[str, int]


def _read_csv_with_fallback(path: Path) -> Tuple[pd.DataFrame, str]:
    last_exc: Exception | None = None
    for encoding in CSV_ENCODINGS:
        try:
            return pd.read_csv(path, encoding=encoding), encoding
        except Exception as exc:
            last_exc = exc
    raise ValueError(f"CSV 读取失败，已尝试 {CSV_ENCODINGS}，最后错误: {last_exc}")


def load_data(file_path: str | Path) -> Tuple[pd.DataFrame, Dict[str, str]]:
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"不支持的文件格式: {path.suffix}")

    info = {"file_name": path.name, "file_type": path.suffix.lower(), "encoding": ""}
    if path.suffix.lower() == ".csv":
        df, enc = _read_csv_with_fallback(path)
        info["encoding"] = enc
    else:
        df = pd.read_excel(path)
        info["encoding"] = "excel"
    return df, info


def _normalize_column_name(name: object) -> str:
    text = str(name).strip()
    if not text or text.lower().startswith("unnamed"):
        return ""
    return text


def _dedupe_columns(columns: Sequence[object]) -> List[str]:
    seen: Dict[str, int] = {}
    result: List[str] = []
    for idx, raw in enumerate(columns, start=1):
        name = _normalize_column_name(raw) or f"未命名字段_{idx}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 0
        result.append(name)
    return result


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    data = df.copy()
    data = data.dropna(how="all").dropna(axis=1, how="all")
    data.columns = _dedupe_columns(list(data.columns))
    for col in data.columns:
        if data[col].dtype == "object":
            data[col] = data[col].astype(str).str.strip()
            data[col] = data[col].replace({"": np.nan, "nan": np.nan, "None": np.nan, "NULL": np.nan})
    if "标准答卷ID" not in data.columns:
        data.insert(0, "标准答卷ID", range(1, len(data) + 1))
    else:
        ordered = ["标准答卷ID"] + [col for col in data.columns if col != "标准答卷ID"]
        data = data[ordered]
    return data


def infer_columns(data: pd.DataFrame) -> Dict[str, List[str]]:
    metadata_columns: List[str] = []
    answer_columns: List[str] = []
    for col in data.columns:
        if col == "标准答卷ID":
            metadata_columns.append(col)
            continue
        if any(keyword.lower() in str(col).lower() for keyword in META_KEYWORDS):
            metadata_columns.append(col)
        else:
            answer_columns.append(col)
    return {"metadata_columns": metadata_columns, "answer_columns": answer_columns}


def _extract_seconds(text: object) -> Optional[float]:
    if text is None or pd.isna(text):
        return None
    if isinstance(text, (int, float, np.integer, np.floating)):
        return float(text)

    raw = str(text).strip()
    if not raw:
        return None

    if re.fullmatch(r"\d+(?:\.\d+)?", raw):
        return float(raw)

    match = re.fullmatch(r"(?:(\d+):)?(\d{1,2}):(\d{1,2})", raw)
    if match:
        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2))
        seconds = int(match.group(3))
        return float(hours * 3600 + minutes * 60 + seconds)

    chinese = re.fullmatch(r"(?:(\d+)小时)?(?:(\d+)分(?:钟)?)?(?:(\d+)秒)?", raw.replace(" ", ""))
    if chinese:
        hours = int(chinese.group(1)) if chinese.group(1) else 0
        minutes = int(chinese.group(2)) if chinese.group(2) else 0
        seconds = int(chinese.group(3)) if chinese.group(3) else 0
        total = hours * 3600 + minutes * 60 + seconds
        return float(total) if total > 0 else None

    if raw.endswith("秒"):
        num = re.sub(r"[^\d.]", "", raw)
        return float(num) if num else None

    return None


def _format_seconds_text(seconds: object) -> Optional[str]:
    value = _extract_seconds(seconds)
    if value is None:
        return None
    if float(value).is_integer():
        return f"{int(value)}秒"
    return f"{round(float(value), 2)}秒"


def detect_duration_column(columns: Sequence[str]) -> Optional[str]:
    priority = ("所用时间", "作答时长", "答题时长", "填写时长", "用时", "耗时")
    for key in priority:
        for col in columns:
            if key in col:
                return col
    return None


def infer_duration_threshold(
    data: pd.DataFrame,
    answer_count: int,
    config: ScreeningConfig,
    duration_col: Optional[str],
) -> float:
    base = float(max(config.min_duration_seconds, answer_count * config.seconds_per_answer))
    if duration_col and duration_col in data.columns:
        parsed = data[duration_col].map(_extract_seconds).dropna()
        if len(parsed) >= 5:
            q10 = float(parsed.quantile(0.10))
            q25 = float(parsed.quantile(0.25))
            return round(max(base, q10 * 0.8, q25 * 0.6), 2)
    return round(base, 2)


def _is_simple_repetition(text: str) -> bool:
    raw = str(text).strip()
    if not raw:
        return False
    if len(set(raw)) <= 1 and len(raw) >= 4:
        return True
    if re.fullmatch(r"(\d)\1{3,}", raw):
        return True
    if re.fullmatch(r"([A-Za-z])\1{3,}", raw):
        return True
    if re.fullmatch(r"([^\w\u4e00-\u9fff])\1{3,}", raw):
        return True
    return False


def _looks_like_nonsense(text: str) -> bool:
    raw = str(text).strip()
    if not raw or raw.lower() in {"nan", "none"}:
        return False
    if raw in {"无", "没有", "不适用", "na", "n/a"}:
        return False
    if _is_simple_repetition(raw):
        return True
    if len(raw) <= 2 and re.fullmatch(r"[a-zA-Z]+", raw):
        return True
    if len(raw) >= 5 and not re.search(r"[\u4e00-\u9fffA-Za-z0-9]", raw):
        return True
    if len(raw) >= 6 and re.fullmatch(r"[A-Za-z0-9]+", raw):
        letters = sum(ch.isalpha() for ch in raw)
        digits = sum(ch.isdigit() for ch in raw)
        return letters > 0 and digits > 0
    return False


def _answer_tokens(values: Iterable[object]) -> List[str]:
    tokens: List[str] = []
    for value in values:
        if pd.isna(value):
            continue
        text = str(value).strip()
        if text:
            tokens.append(text)
    return tokens


def _same_answer_ratio(tokens: Sequence[str]) -> float:
    if not tokens:
        return 0.0
    counts = pd.Series(tokens).value_counts()
    return float(counts.iloc[0] / len(tokens))


def _entropy(tokens: Sequence[str]) -> float:
    if not tokens:
        return 0.0
    counts = pd.Series(tokens).value_counts(normalize=True)
    return float(-(counts * np.log2(counts)).sum())


def classify_row(
    row: pd.Series,
    answer_columns: Sequence[str],
    metadata_columns: Sequence[str],
    duration_col: Optional[str],
    duration_threshold: float,
    config: ScreeningConfig,
) -> Tuple[bool, List[str], Dict[str, object]]:
    reasons: List[str] = []
    details: Dict[str, object] = {}

    answers = _answer_tokens(row[col] for col in answer_columns)
    answered_count = len(answers)
    missing_count = len(answer_columns) - answered_count
    missing_ratio = missing_count / len(answer_columns) if answer_columns else 1.0
    details["answered_count"] = answered_count
    details["missing_count"] = missing_count
    details["missing_ratio"] = round(missing_ratio, 4)

    duration_seconds = _extract_seconds(row[duration_col]) if duration_col and duration_col in row.index else None
    details["duration_seconds"] = duration_seconds

    if duration_seconds is not None and duration_seconds < duration_threshold:
        reasons.append("作答时长过短")

    if missing_ratio >= config.missing_threshold:
        reasons.append("大面积缺答")

    if answered_count >= config.minimum_answered_for_uniform:
        unique_answers = len(set(answers))
        same_ratio = _same_answer_ratio(answers)
        entropy = _entropy(answers)
        details["same_answer_ratio"] = round(same_ratio, 4)
        details["answer_entropy"] = round(entropy, 4)
        if unique_answers == 1:
            reasons.append("统一答案")
        elif same_ratio >= config.uniform_ratio_threshold and entropy <= 0.75:
            reasons.append("疑似直线作答")

    text_answers = [x for x in answers if isinstance(x, str)]
    nonsense_hits = sum(1 for x in text_answers if _looks_like_nonsense(x))
    nonsense_ratio = nonsense_hits / len(text_answers) if text_answers else 0.0
    details["nonsense_hits"] = nonsense_hits
    details["nonsense_ratio"] = round(nonsense_ratio, 4)
    if len(text_answers) >= config.min_text_answers_for_nonsense and nonsense_ratio >= config.nonsense_ratio_threshold:
        reasons.append("无意义乱填")

    if "标准答卷ID" in row.index:
        details["standard_id"] = row["标准答卷ID"]
    for col in metadata_columns:
        if col in row.index and col != "标准答卷ID" and col not in details:
            details[col] = row[col]

    return bool(reasons), reasons, details


def screen_questionnaires(
    data: pd.DataFrame,
    config: Optional[ScreeningConfig] = None,
    column_info: Optional[Dict[str, List[str]]] = None,
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, ScreeningResult, Dict[str, object]]:
    config = config or ScreeningConfig()
    columns = column_info or infer_columns(data)
    metadata_columns = columns["metadata_columns"]
    answer_columns = columns["answer_columns"]
    duration_col = detect_duration_column(data.columns)
    duration_threshold = infer_duration_threshold(data, len(answer_columns), config, duration_col)

    logs: List[Dict[str, object]] = []
    reasons_all: List[Dict[str, object]] = []
    valid_idx: List[int] = []
    invalid_idx: List[int] = []

    for idx, row in data.iterrows():
        invalid, reasons, details = classify_row(
            row=row,
            answer_columns=answer_columns,
            metadata_columns=metadata_columns,
            duration_col=duration_col,
            duration_threshold=duration_threshold,
            config=config,
        )
        reason_text = "；".join(reasons) if reasons else ""
        log_row = {
            "标准答卷ID": row.get("标准答卷ID", idx + 1),
            "行号": idx + 2,
            "是否剔除": "是" if invalid else "否",
            "剔除原因": reason_text,
            "作答时长秒": details.get("duration_seconds"),
            "答题数": details.get("answered_count"),
            "缺答数": details.get("missing_count"),
            "缺答率": details.get("missing_ratio"),
            "乱填率": details.get("nonsense_ratio"),
            "统一度": details.get("same_answer_ratio"),
            "回答熵": details.get("answer_entropy"),
        }
        for col in metadata_columns:
            if col in row.index and col not in log_row:
                log_row[col] = row[col]
        logs.append(log_row)

        if invalid:
            invalid_idx.append(idx)
        else:
            valid_idx.append(idx)

        for reason in reasons:
            reasons_all.append({"标准答卷ID": log_row["标准答卷ID"], "原因": reason})

    valid_df = data.loc[valid_idx].copy().reset_index(drop=True)
    invalid_df = data.loc[invalid_idx].copy().reset_index(drop=True)
    log_df = pd.DataFrame(logs)
    reason_df = pd.DataFrame(reasons_all)

    total = len(data)
    invalid_count = len(invalid_df)
    valid_count = len(valid_df)
    reason_breakdown = reason_df["原因"].value_counts().to_dict() if not reason_df.empty else {}
    nonresponse_error_rate = reason_breakdown.get("大面积缺答", 0) / total if total else 0.0
    non_sampling_error_rate = invalid_count / total if total else 0.0

    result = ScreeningResult(
        total_rows=total,
        valid_rows=valid_count,
        invalid_rows=invalid_count,
        valid_rate=round(valid_count / total, 4) if total else 0.0,
        invalid_rate=round(invalid_count / total, 4) if total else 0.0,
        non_sampling_error_rate=round(non_sampling_error_rate, 4),
        nonresponse_error_rate=round(nonresponse_error_rate, 4),
        duration_threshold_seconds=duration_threshold,
        missing_threshold=config.missing_threshold,
        reason_breakdown=reason_breakdown,
    )
    context = {
        "metadata_columns": metadata_columns,
        "answer_columns": answer_columns,
        "duration_column": duration_col,
        "config": asdict(config),
    }
    return valid_df, invalid_df, log_df, result, context


def clean_valid_data(
    valid_df: pd.DataFrame,
    column_info: Dict[str, List[str]],
    duration_col: Optional[str],
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    对筛查后的有效样本做进一步清洗：
    1. 再次统一字符串格式
    2. 派生作答时长秒数
    3. 删除完全重复记录
    4. 输出清洗步骤报告
    """
    cleaned = valid_df.copy()
    steps: List[Dict[str, object]] = []

    before = len(cleaned)
    object_cols = [c for c in cleaned.columns if cleaned[c].dtype == "object"]
    for col in object_cols:
        cleaned[col] = cleaned[col].astype(str).str.strip()
        cleaned[col] = cleaned[col].replace({"": np.nan, "nan": np.nan, "None": np.nan, "NULL": np.nan})
    steps.append({
        "步骤": "文本标准化",
        "清洗前数量": before,
        "清洗后数量": len(cleaned),
        "说明": "再次统一空值、空格和字符串格式",
    })

    before = len(cleaned)
    duration_seconds_col = None
    if duration_col and duration_col in cleaned.columns:
        duration_seconds_col = "作答时长秒"
        cleaned[duration_seconds_col] = cleaned[duration_col].map(_extract_seconds)
        cleaned[duration_col] = cleaned[duration_col].map(_format_seconds_text)
        steps.append({
            "步骤": "时长转换",
            "清洗前数量": before,
            "清洗后数量": len(cleaned),
            "说明": f"将 {duration_col} 统一显示为秒文本，并生成 {duration_seconds_col}",
        })

    before = len(cleaned)
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    removed = before - len(cleaned)
    steps.append({
        "步骤": "重复样本去除",
        "清洗前数量": before,
        "清洗后数量": len(cleaned),
        "说明": f"删除完全重复记录 {removed} 条",
    })

    if duration_seconds_col and duration_seconds_col in cleaned.columns:
        front_cols = ["标准答卷ID", duration_col, duration_seconds_col]
        ordered = [c for c in front_cols if c in cleaned.columns] + [c for c in cleaned.columns if c not in front_cols]
        cleaned = cleaned[ordered]

    report = pd.DataFrame(steps)
    return cleaned, report


def _write_csv(df: pd.DataFrame, path: Path) -> None:
    df.to_csv(path, index=False, encoding="utf-8-sig")


def _build_summary_frame(result: ScreeningResult) -> pd.DataFrame:
    rows = [
        ("总问卷数", result.total_rows),
        ("有效问卷数", result.valid_rows),
        ("无效问卷数", result.invalid_rows),
        ("有效率", result.valid_rate),
        ("无效率", result.invalid_rate),
        ("非抽样误差率", result.non_sampling_error_rate),
        ("无回答误差率", result.nonresponse_error_rate),
        ("时长阈值(秒)", result.duration_threshold_seconds),
        ("缺答阈值", result.missing_threshold),
    ]
    return pd.DataFrame(rows, columns=["指标", "数值"])


def _build_reason_frame(result: ScreeningResult) -> pd.DataFrame:
    if not result.reason_breakdown:
        return pd.DataFrame(columns=["原因", "次数", "占比"])
    total = result.total_rows or 1
    return pd.DataFrame(
        [
            {"原因": reason, "次数": count, "占比": round(count / total, 4)}
            for reason, count in sorted(result.reason_breakdown.items(), key=lambda item: item[1], reverse=True)
        ]
    )


def save_outputs(
    output_dir: str | Path,
    raw_df: pd.DataFrame,
    valid_df: pd.DataFrame,
    cleaned_df: pd.DataFrame,
    invalid_df: pd.DataFrame,
    log_df: pd.DataFrame,
    cleaning_report: pd.DataFrame,
    result: ScreeningResult,
    context: Dict[str, object],
    source_file: str,
    copy_source: Optional[Path] = None,
) -> Dict[str, Path]:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    if copy_source is not None and copy_source.exists():
        shutil.copy2(copy_source, out / f"source_{copy_source.name}")

    _write_csv(raw_df, out / "raw_data_snapshot.csv")
    _write_csv(valid_df, out / "cleaned_data.csv")
    _write_csv(cleaning_report, out / "cleaning_report.csv")
    _write_csv(cleaned_df, out / "final_cleaned_data.csv")
    _write_csv(invalid_df, out / "invalid_data.csv")
    _write_csv(log_df, out / "filter_log.csv")
    _write_csv(_build_summary_frame(result), out / "error_report.csv")
    _write_csv(_build_reason_frame(result), out / "reason_statistics.csv")

    with open(out / "screening_schema.json", "w", encoding="utf-8") as f:
        json.dump(
            {
                "module_name": "无效问卷筛查与误差统计",
                "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source_file": source_file,
                "context": context,
                "result": asdict(result),
                "outputs": {
                    "raw_data_snapshot.csv": "原始数据快照，便于回溯核对",
                    "cleaned_data.csv": "筛查后有效样本",
                    "cleaning_report.csv": "清洗步骤报告",
                    "final_cleaned_data.csv": "完成清洗后的最终标准数据",
                    "invalid_data.csv": "被剔除问卷",
                    "filter_log.csv": "逐份问卷过滤原因日志",
                    "error_report.csv": "非抽样误差与无回答误差统计",
                    "reason_statistics.csv": "各剔除原因的次数和占比",
                },
            },
            f,
            ensure_ascii=False,
            indent=2,
        )

    with open(out / "run_log.txt", "w", encoding="utf-8") as f:
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 开始处理: {source_file}\n")
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 总问卷数: {result.total_rows}\n")
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 有效问卷数: {result.valid_rows}\n")
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 无效问卷数: {result.invalid_rows}\n")
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 时长阈值(秒): {result.duration_threshold_seconds}\n")
        f.write(f"[{datetime.now():%Y-%m-%d %H:%M:%S}] 生成目录: {out.resolve()}\n")

    return {
        "raw_data_snapshot.csv": out / "raw_data_snapshot.csv",
        "cleaned_data.csv": out / "cleaned_data.csv",
        "cleaning_report.csv": out / "cleaning_report.csv",
        "final_cleaned_data.csv": out / "final_cleaned_data.csv",
        "invalid_data.csv": out / "invalid_data.csv",
        "filter_log.csv": out / "filter_log.csv",
        "error_report.csv": out / "error_report.csv",
        "reason_statistics.csv": out / "reason_statistics.csv",
        "screening_schema.json": out / "screening_schema.json",
        "run_log.txt": out / "run_log.txt",
    }


def process_file(
    file_path: str | Path,
    output_dir: str | Path = "output_group2",
    config: Optional[ScreeningConfig] = None,
) -> Dict[str, object]:
    raw_df, read_info = load_data(file_path)
    normalized = normalize_dataframe(raw_df)
    column_info = infer_columns(normalized)
    valid_df, invalid_df, log_df, result, context = screen_questionnaires(
        normalized,
        config=config,
        column_info=column_info,
    )
    cleaned_df, cleaning_report = clean_valid_data(
        valid_df=valid_df,
        column_info=column_info,
        duration_col=context["duration_column"],
    )
    output_paths = save_outputs(
        output_dir=output_dir,
        raw_df=normalized,
        valid_df=valid_df,
        cleaned_df=cleaned_df,
        invalid_df=invalid_df,
        log_df=log_df,
        cleaning_report=cleaning_report,
        result=result,
        context={**context, "read_info": read_info},
        source_file=Path(file_path).name,
        copy_source=Path(file_path),
    )
    return {
        "raw_data": normalized,
        "clean_data": valid_df,
        "final_cleaned_data": cleaned_df,
        "cleaning_report": cleaning_report,
        "invalid_data": invalid_df,
        "filter_log": log_df,
        "screening_result": result,
        "column_info": column_info,
        "read_info": read_info,
        "output_paths": output_paths,
        "output_dir": Path(output_dir),
    }


def launch_interactive_gui(default_output_dir: str = "output_group2") -> bool:
    try:
        import tkinter as tk
        from tkinter import filedialog, messagebox
    except Exception:
        return False

    root = tk.Tk()
    root.title("组员2 - 无效问卷筛查与误差统计")
    root.geometry("760x430")
    root.minsize(720, 400)

    file_var = tk.StringVar()
    output_var = tk.StringVar(value=default_output_dir)
    status_var = tk.StringVar(value="请选择问卷文件并点击开始筛查。")

    def browse_file() -> None:
        path = filedialog.askopenfilename(
            title="请选择问卷文件",
            filetypes=[
                ("Excel files", "*.xlsx *.xls *.xlsm"),
                ("CSV files", "*.csv"),
                ("All files", "*.*"),
            ],
        )
        if path:
            file_var.set(path)

    def run_screening() -> None:
        file_path = file_var.get().strip().strip('"')
        output_dir = output_var.get().strip() or default_output_dir
        if not file_path:
            messagebox.showwarning("提示", "请先选择或输入文件路径。")
            return

        try:
            status_var.set("正在处理，请稍候...")
            root.update_idletasks()
            result = process_file(file_path, output_dir=output_dir)
            summary = result["screening_result"]
            status_var.set("处理完成。")
            result_box.delete("1.0", tk.END)
            result_box.insert(
                tk.END,
                "\n".join(
                    [
                        f"总问卷数: {summary.total_rows}",
                        f"有效问卷数: {summary.valid_rows}",
                        f"无效问卷数: {summary.invalid_rows}",
                        f"有效率: {summary.valid_rate:.2%}",
                        f"无效率: {summary.invalid_rate:.2%}",
                        f"清洗后有效样本数: {len(result['final_cleaned_data'])}",
                        f"输出目录: {Path(result['output_dir']).resolve()}",
                    ]
                ),
            )
        except Exception as exc:
            status_var.set("处理失败。")
            messagebox.showerror("运行失败", str(exc))

    tk.Label(root, text="无效问卷筛查与误差统计", font=("Microsoft YaHei", 16, "bold")).pack(pady=(14, 4))
    tk.Label(root, text="支持 CSV / Excel 文件，输入路径后点击开始筛查。", font=("Microsoft YaHei", 10)).pack(pady=(0, 10))

    form = tk.Frame(root)
    form.pack(fill="x", padx=18, pady=8)
    tk.Label(form, text="文件路径", width=10, anchor="w").grid(row=0, column=0, sticky="w", pady=6)
    tk.Entry(form, textvariable=file_var).grid(row=0, column=1, sticky="ew", padx=(0, 8), pady=6)
    tk.Button(form, text="浏览", command=browse_file, width=10).grid(row=0, column=2, pady=6)

    tk.Label(form, text="输出目录", width=10, anchor="w").grid(row=1, column=0, sticky="w", pady=6)
    tk.Entry(form, textvariable=output_var).grid(row=1, column=1, sticky="ew", padx=(0, 8), pady=6)
    tk.Label(form, text="").grid(row=1, column=2, pady=6)
    form.columnconfigure(1, weight=1)

    button_bar = tk.Frame(root)
    button_bar.pack(fill="x", padx=18, pady=(8, 6))
    tk.Button(button_bar, text="开始筛查", command=run_screening, width=14).pack(side="left")
    tk.Label(button_bar, textvariable=status_var, anchor="w").pack(side="left", padx=14)

    tk.Label(root, text="运行结果", font=("Microsoft YaHei", 11, "bold")).pack(anchor="w", padx=18, pady=(10, 4))
    result_box = tk.Text(root, height=10, wrap="word")
    result_box.pack(fill="both", expand=True, padx=18, pady=(0, 14))
    result_box.insert("1.0", "等待运行结果...")

    root.mainloop()
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="无效问卷筛查与误差统计")
    parser.add_argument("file_path", nargs="?", help="问卷文件路径（CSV/Excel）")
    parser.add_argument("-o", "--output-dir", default="output_group2", help="输出目录")
    args = parser.parse_args()

    file_path = (args.file_path or "").strip().strip('"')
    if not file_path:
        if launch_interactive_gui(default_output_dir=args.output_dir):
            return
        print("无法启动图形界面，请改用命令行参数：python group2_invalid_questionnaire_screening.py <文件路径>")
        return

    print("=" * 60)
    print("组员2：无效问卷筛查与误差统计")
    print("支持 CSV / Excel 输入，自动输出清洗结果、过滤日志和误差报表")
    print("=" * 60)

    try:
        result = process_file(file_path, output_dir=args.output_dir)
        summary = result["screening_result"]
        print("\n处理完成")
        print(f"总问卷数: {summary.total_rows}")
        print(f"有效问卷数: {summary.valid_rows}")
        print(f"无效问卷数: {summary.invalid_rows}")
        print(f"有效率: {summary.valid_rate:.2%}")
        print(f"无效率: {summary.invalid_rate:.2%}")
        print(f"输出目录: {Path(result['output_dir']).resolve()}")
    except Exception as exc:
        print(f"\n运行失败: {exc}")


if __name__ == "__main__":
    main()
