# -*- coding: utf-8 -*-
"""
综合报告生成系统
功能：
1. 对接全模块数据，为单选、多选、量表批量生成饼图、直方图
2. 实现图表样式自适应调整，自动搭配标准化分析文案
3. 开发多格式报告导出功能，整合数据、图表、文字形成完整报告
4. 汇总所有代码模块，完成系统整体拼接整合
"""

from __future__ import annotations

import io
import json
import math
import os
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import streamlit as st
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm   # <-- 新添加的
try:
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    PLOTLIB_AVAILABLE = True
except ImportError:
    PLOTLIB_AVAILABLE = False

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, letter
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import inch, mm
    from reportlab.platypus import (Image as RLImage, Paragraph, SimpleDocTemplate,
                                   Spacer, Table, TableStyle)
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False

try:
    from docx import Document
    from docx.shared import Inches, Pt, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False


CHINESE_FONTS = [
    "SimHei", "Microsoft YaHei", "SimSun", "STHeiti", "WenQuanYi Micro Hei",
    "Noto Sans CJK SC", "Source Han Sans CN", "PingFang SC", "Heiti SC"
]

DEFAULT_FONT = "SimHei"
for font in CHINESE_FONTS:
    if any(font in f.name for f in fm.fontManager.ttflist if hasattr(f, 'name')):
        DEFAULT_FONT = font
        break


@dataclass
class ChartConfig:
    width: int = 10
    height: int = 6
    dpi: int = 150
    title_fontsize: int = 14
    label_fontsize: int = 10
    legend_fontsize: int = 9
    color_scheme: str = "default"
    style: str = "seaborn-v0_8-darkgrid"
    max_categories: int = 10
    min_bar_height: float = 0.02
    pie_label_distance: float = 1.1
    histogram_bins: int = 10
    show_values: bool = True
    value_format: str = ".1%"
    grid_alpha: float = 0.3


@dataclass
class QuestionTypeResult:
    question_name: str
    question_id: str
    question_type: str
    valid_responses: int
    missing_count: int
    missing_rate: float
    frequency_table: Dict[str, int]
    percentage_table: Dict[str, float]
    cumulative_table: Dict[str, float]
    central_tendency: Dict[str, float]
    dispersion: Dict[str, float]
    chart_path: Optional[str] = None
    analysis_text: str = ""


@dataclass
class LikertScaleResult:
    dimension_name: str
    item_columns: List[str]
    dimension_mean: float
    dimension_std: float
    dimension_variance: float
    dimension_median: float
    dimension_min: float
    dimension_max: float
    dimension_range: float
    cronbach_alpha: float
    item_statistics: List[Dict] = field(default_factory=list)
    chart_path: Optional[str] = None
    analysis_text: str = ""


@dataclass
class ComprehensiveReport:
    report_title: str
    generated_at: str
    data_source: str
    total_respondents: int
    valid_respondents: int
    response_rate: float
    single_choice_results: List[QuestionTypeResult] = field(default_factory=list)
    multiple_choice_results: List[QuestionTypeResult] = field(default_factory=list)
    likert_scale_results: List[LikertScaleResult] = field(default_factory=list)
    overall_analysis: str = ""
    chart_output_dir: str = ""
    data_summary: Dict = field(default_factory=dict)


CHART_COLORS = {
    "default": ["#4E79A7", "#F28E2B", "#E15759", "#76B7B2", "#59A14F",
                "#EDC948", "#B07AA1", "#FF9DA7", "#9C755F", "#BAB0AC"],
    "professional": ["#2C3E50", "#3498DB", "#E74C3C", "#27AE60", "#F39C12",
                     "#9B59B6", "#1ABC9C", "#E91E63", "#00BCD4", "#8BC34A"],
    "warm": ["#D35400", "#E67E22", "#F39C12", "#F1C40F", "#2ECC71",
             "#1ABC9C", "#16A085", "#2980B9", "#8E44AD", "#C0392B"],
    "cool": ["#1F77B4", "#4ECDC4", "#45B7D1", "#96CEB4", "#FFEAA7",
             "#DDA0DD", "#98D8C8", "#F7DC6F", "#BB8FCE", "#85C1E2"],
    "pastel": ["#FFB3BA", "#FFDFBA", "#FFFFBA", "#BAFFC9", "#BAE1FF",
               "#E0BBE4", "#FEC8D8", "#D4F0F0", "#FFE5B4", "#C9E4DE"],
}


LIKERT_SCALE_LABELS = {
    5: {1: "非常不同意", 2: "不同意", 3: "中立", 4: "同意", 5: "非常同意"},
    7: {1: "非常不同意", 2: "不同意", 3: "比较不同意", 4: "中立", 5: "比较同意", 6: "同意", 7: "非常同意"},
    6: {1: "非常不同意", 2: "不同意", 3: "有点不同意", 4: "有点同意", 5: "同意", 6: "非常同意"},
}


def setup_chinese_font():
    if not PLOTLIB_AVAILABLE:
        return "DejaVu Sans"
    for font in CHINESE_FONTS:
        font_candidates = fm.findSystemFonts(fontpaths=None, fontext='ttf')
        for font_path in font_candidates:
            if font.lower() in font_path.lower():
                try:
                    fm.fontManager.addfont(font_path)
                    prop = fm.FontProperties(fname=font_path)
                    plt.rcParams['font.family'] = prop.get_name()
                    return prop.get_name()
                except Exception:
                    pass
    plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
    plt.rcParams['axes.unicode_minus'] = False
    return plt.rcParams['font.sans-serif'][0]


CHART_FONT = setup_chinese_font()


def detect_question_type(series: pd.Series, column_name: str = "") -> str:
    if series.dtype == 'object' or str(series.dtype) == 'string':
        unique_vals = series.dropna().unique()
        sample_size = min(20, len(unique_vals))
        sample = list(unique_vals[:sample_size]) if len(unique_vals) > 0 else []

        for val in sample:
            val_str = str(val).strip()
            if ',' in val_str or '；' in val_str or '、' in val_str:
                return "multiple_choice"

        if len(unique_vals) <= 15:
            numeric_convertible = 0
            for val in sample:
                try:
                    float(str(val).strip())
                    numeric_convertible += 1
                except (ValueError, TypeError):
                    pass
            if numeric_convertible / max(len(sample), 1) > 0.6:
                if all(1 <= float(str(v).strip()) <= 5 or 1 <= float(str(v).strip()) <= 7 for v in sample if str(v).strip()):
                    try:
                        vals = [float(v) for v in unique_vals if str(v).strip()]
                        if min(vals) >= 1 and max(vals) <= 7 and len(vals) <= 7:
                            return "likert_scale"
                    except (ValueError, TypeError):
                        pass

    unique_count = series.dropna().nunique()
    if unique_count <= 8:
        return "single_choice"

    if 1 <= series.dropna().min() <= 7 and 1 <= series.dropna().max() <= 7:
        return "likert_scale"

    return "text"


def infer_likert_points(series: pd.Series) -> int:
    vals = series.dropna().unique()
    int_vals = []
    for v in vals:
        try:
            int_vals.append(int(float(str(v).strip())))
        except (ValueError, TypeError):
            pass
    if not int_vals:
        return 5
    min_val, max_val = min(int_vals), max(int_vals)
    if min_val >= 1 and max_val <= 5:
        return 5
    elif min_val >= 1 and max_val <= 7:
        return 7
    elif min_val >= 1 and max_val <= 6:
        return 6
    return 5


def calculate_frequency_stats(series: pd.Series) -> Tuple[Dict, Dict, Dict]:
    freq = series.value_counts(dropna=False).to_dict()
    total = len(series)
    freq_clean = {k: v for k, v in freq.items() if pd.notna(k) and str(k).strip() not in ['', 'nan', 'None', 'NA']}
    pct = {k: round(v / sum(freq_clean.values()), 4) for k, v in freq_clean.items()}
    sorted_items = sorted(freq_clean.items(), key=lambda x: x[1], reverse=True)
    cum_pct = {}
    cum_sum = 0
    for k, v in sorted_items:
        cum_sum += v
        cum_pct[k] = round(cum_sum / sum(freq_clean.values()), 4)
    return freq_clean, pct, cum_pct


def calculate_central_tendency(series: pd.Series) -> Dict[str, float]:
    clean = pd.to_numeric(series, errors='coerce').dropna()
    if len(clean) == 0:
        return {"mean": 0, "median": 0, "mode": 0}
    return {
        "mean": round(float(clean.mean()), 3),
        "median": round(float(clean.median()), 3),
        "mode": round(float(clean.mode().iloc[0]) if len(clean.mode()) > 0 else 0, 3),
    }


def calculate_dispersion(series: pd.Series) -> Dict[str, float]:
    clean = pd.to_numeric(series, errors='coerce').dropna()
    if len(clean) == 0:
        return {"std": 0, "variance": 0, "range": 0, "min": 0, "max": 0, "q1": 0, "q3": 0, "iqr": 0}
    return {
        "std": round(float(clean.std()), 3),
        "variance": round(float(clean.var()), 3),
        "range": round(float(clean.max() - clean.min()), 3),
        "min": round(float(clean.min()), 3),
        "max": round(float(clean.max()), 3),
        "q1": round(float(clean.quantile(0.25)), 3),
        "q3": round(float(clean.quantile(0.75)), 3),
        "iqr": round(float(clean.quantile(0.75) - clean.quantile(0.25)), 3),
    }


def generate_analysis_text(result: QuestionTypeResult) -> str:
    q_name = result.question_name
    q_type = result.question_type
    n = result.valid_responses
    miss = result.missing_count
    miss_rate = result.missing_rate
    freq = result.frequency_table
    pct = result.percentage_table
    ct = result.central_tendency
    disp = result.dispersion

    if q_type == "single_choice":
        sorted_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
        top_option = sorted_items[0][0] if sorted_items else "未知"
        top_pct = pct.get(top_option, 0)

        text = f"本题共收到{n}份有效回答，缺失{miss}份（缺失率{miss_rate:.1%}）。"
        text += f"\n从频数分布来看，{top_option}选项选择人数最多，占比{top_pct:.1%}，"
        if top_pct > 0.5:
            text += f"表明该选项具有明显集中趋势。"
        elif top_pct > 0.3:
            text += f"分布较为集中。"
        else:
            text += f"各选项分布相对均衡。"
        text += f"\n均值={ct['mean']:.2f}，标准差={disp['std']:.2f}，说明回答离散程度{'较低' if disp['std'] < 1 else '中等' if disp['std'] < 2 else '较高'}。"
        return text

    elif q_type == "multiple_choice":
        total_selections = sum(freq.values())
        avg_per_person = total_selections / n if n > 0 else 0
        sorted_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:3]
        top_options = [f"{k}（{pct[k]:.1%}）" for k, v in sorted_items]

        text = f"本题为多选题，共收集{total_selections}次选择，"
        text += f"人均选择{round(avg_per_person, 1)}个选项，有效回答{n}份。"
        text += f"\n选择比例最高的三个选项依次为：{'；'.join(top_options)}。"
        return text

    elif q_type == "likert_scale":
        text = f"本题为量表题，有效回答{n}份，缺失{miss}份（缺失率{miss_rate:.1%}）。"
        text += f"\n均值={ct['mean']:.3f}，中位数={ct['median']:.3f}，标准差={disp['std']:.3f}。"
        if ct['mean'] >= 4:
           倾向 = "偏向正向（同意）"
        elif ct['mean'] >= 3:
            倾向 = "偏向中立"
        else:
            倾向 = "偏向负向（不同意）"
        text += f"整体{倾向}，"
        text += f"回答分布在Q1={disp['q1']:.1f}至Q3={disp['q3']:.1f}之间（四分位距={disp['iqr']:.1f}），"
        text += f"数据离散程度{'较低' if disp['std'] < 0.8 else '中等' if disp['std'] < 1.2 else '较高'}。"
        return text

    return f"本题有效回答{n}份，缺失{miss}份。"


def plot_single_choice_pie(series: pd.Series, title: str, config: ChartConfig,
                           output_path: str, color_scheme: List[str]) -> bool:
    if not PLOTLIB_AVAILABLE:
        return False
    freq, pct, _ = calculate_frequency_stats(series)
    if not freq:
        return False

    labels = [str(k) for k in freq.keys()]
    sizes = list(freq.values())
    percentages = [pct[k] for k in freq.keys()]

    if len(labels) > config.max_categories:
        sorted_items = sorted(zip(labels, sizes, percentages), key=lambda x: x[1], reverse=True)
        top_n = sorted_items[:config.max_categories - 1]
        others_sum = sum(v for _, v, _ in sorted_items[config.max_categories - 1:])
        others_pct = sum(p for _, _, p in sorted_items[config.max_categories - 1:])
        labels = [str(x[0]) for x in top_n] + ['其他']
        sizes = [x[1] for x in top_n] + [others_sum]
        percentages = [x[2] for x in top_n] + [others_pct]

    fig, ax = plt.subplots(figsize=(config.width, config.height), dpi=config.dpi)

    colors = color_scheme[:len(labels)]
    if len(labels) > len(colors):
        colors = (colors * ((len(labels) // len(colors)) + 1))[:len(labels)]

    wedges, texts, autotexts = ax.pie(
        sizes,
        labels=None,
        autopct=lambda pct: f'{pct:.1f}%' if pct > 3 else '',
        startangle=90,
        colors=colors,
        pctdistance=0.75,
        wedgeprops=dict(width=0.6, edgecolor='white', linewidth=2)
    )

    for autotext in autotexts:
        autotext.set_fontsize(config.label_fontsize)
        autotext.set_fontweight('bold')

    ax.set_title(title, fontsize=config.title_fontsize, fontweight='bold', pad=20)

    legend_labels = [f'{l}: {p:.1%}' for l, p in zip(labels, percentages)]
    ax.legend(wedges, legend_labels, title="选项分布", loc="center left",
              bbox_to_anchor=(1, 0, 0.5, 1), fontsize=config.legend_fontsize)

    plt.tight_layout()
    plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return True


def plot_single_choice_bar(series: pd.Series, title: str, config: ChartConfig,
                           output_path: str, color_scheme: List[str],
                           horizontal: bool = True) -> bool:
    if not PLOTLIB_AVAILABLE:
        return False
    freq, pct, _ = calculate_frequency_stats(series)
    if not freq:
        return False

    sorted_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    labels = [str(k) for k, v in sorted_items]
    sizes = [v for k, v in sorted_items]
    percentages = [pct[k] for k, v in sorted_items]

    if len(labels) > config.max_categories:
        sorted_items = sorted_items[:config.max_categories]
        labels = [str(k) for k, v in sorted_items]
        sizes = [v for k, v in sorted_items]
        percentages = [pct[k] for k, v in sorted_items]

    fig, ax = plt.subplots(figsize=(config.width, config.height), dpi=config.dpi)

    colors = color_scheme[:len(labels)]
    if len(labels) > len(colors):
        colors = (colors * ((len(labels) // len(colors)) + 1))[:len(labels)]

    if horizontal:
        bars = ax.barh(labels, sizes, color=colors, edgecolor='white', linewidth=1.5, height=0.6)
        ax.set_xlabel('频数', fontsize=config.label_fontsize)
        ax.invert_yaxis()
    else:
        bars = ax.bar(labels, sizes, color=colors, edgecolor='white', linewidth=1.5, width=0.6)
        ax.set_ylabel('频数', fontsize=config.label_fontsize)
        plt.xticks(rotation=45, ha='right')

    ax.set_title(title, fontsize=config.title_fontsize, fontweight='bold', pad=15)
    ax.grid(axis='y' if horizontal else 'x', alpha=config.grid_alpha, linestyle='--')

    for i, (bar, pct_val) in enumerate(zip(bars, percentages)):
        if horizontal:
            width = bar.get_width()
            ax.text(width + max(sizes) * 0.01, bar.get_y() + bar.get_height() / 2,
                    f'{pct_val:.1%}', va='center', fontsize=config.legend_fontsize)
        else:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, height + max(sizes) * 0.01,
                    f'{pct_val:.1%}', ha='center', va='bottom', fontsize=config.legend_fontsize)

    plt.tight_layout()
    plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return True


def plot_multiple_choice_bar(series: pd.Series, title: str, config: ChartConfig,
                              output_path: str, color_scheme: List[str]) -> bool:
    if not PLOTLIB_AVAILABLE:
        return False
    all_choices = []
    for val in series.dropna():
        parts = re.split(r'[,，；;、]', str(val))
        all_choices.extend([p.strip() for p in parts if p.strip()])

    if not all_choices:
        return False

    freq = pd.Series(all_choices).value_counts().to_dict()
    total_selections = len(all_choices)
    pct = {k: v / total_selections for k, v in freq.items()}

    sorted_items = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    labels = [str(k) for k, v in sorted_items]
    sizes = [v for k, v in sorted_items]
    percentages = [pct[k] for k, v in sorted_items]

    if len(labels) > config.max_categories:
        sorted_items = sorted_items[:config.max_categories]
        labels = [str(k) for k, v in sorted_items]
        sizes = [v for k, v in sorted_items]
        percentages = [pct[k] for k, v in sorted_items]

    fig, ax = plt.subplots(figsize=(config.width, config.height), dpi=config.dpi)

    colors = color_scheme[:len(labels)]
    colors = (colors * ((len(labels) // len(colors)) + 1))[:len(labels)]

    bars = ax.barh(labels, sizes, color=colors, edgecolor='white', linewidth=1.5, height=0.6)
    ax.set_xlabel('选择次数', fontsize=config.label_fontsize)
    ax.invert_yaxis()
    ax.set_title(title, fontsize=config.title_fontsize, fontweight='bold', pad=15)
    ax.grid(axis='y', alpha=config.grid_alpha, linestyle='--')

    for bar, pct_val in zip(bars, percentages):
        width = bar.get_width()
        ax.text(width + max(sizes) * 0.01, bar.get_y() + bar.get_height() / 2,
                f'{pct_val:.1%}', va='center', fontsize=config.legend_fontsize)

    plt.tight_layout()
    plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return True


def plot_likert_histogram(series: pd.Series, title: str, config: ChartConfig,
                           output_path: str, color_scheme: List[str]) -> bool:
    if not PLOTLIB_AVAILABLE:
        return False
    clean = pd.to_numeric(series, errors='coerce').dropna()
    if len(clean) == 0:
        return False

    n_points = infer_likert_points(series)
    point_labels = LIKERT_SCALE_LABELS.get(n_points, LIKERT_SCALE_LABELS[5])

    fig, ax = plt.subplots(figsize=(config.width, config.height), dpi=config.dpi)

    counts, bins, patches = ax.hist(clean, bins=n_points, range=(0.5, n_points + 0.5),
                                     edgecolor='white', linewidth=2, align='mid')

    norm_counts = counts / len(clean)
    for patch, norm_count in zip(patches, norm_counts):
        height = patch.get_height()
        if norm_count >= 0.1:
            patch.set_facecolor(color_scheme[0])
        elif norm_count >= 0.05:
            patch.set_facecolor(color_scheme[1])
        else:
            patch.set_facecolor(color_scheme[2])
        ax.text(patch.get_x() + patch.get_width() / 2, height + len(clean) * 0.01,
                f'{norm_count:.1%}', ha='center', va='bottom', fontsize=config.label_fontsize)

    ax.set_xticks(range(1, n_points + 1))
    ax.set_xticklabels([point_labels.get(i, str(i)) for i in range(1, n_points + 1)], fontsize=config.label_fontsize)
    ax.set_xlabel('选项', fontsize=config.label_fontsize)
    ax.set_ylabel('频数', fontsize=config.label_fontsize)
    ax.set_title(title, fontsize=config.title_fontsize, fontweight='bold', pad=15)
    ax.grid(axis='y', alpha=config.grid_alpha, linestyle='--')

    mean_val = clean.mean()
    ax.axvline(mean_val, color='red', linestyle='--', linewidth=2, label=f'均值={mean_val:.2f}')
    ax.legend(fontsize=config.legend_fontsize)

    plt.tight_layout()
    plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return True


def plot_likert_stacked_bar(results: List[LikertScaleResult], title: str,
                             config: ChartConfig, output_path: str,
                             color_scheme: List[str]) -> bool:
    if not PLOTLIB_AVAILABLE or not results:
        return False

    n_points = 5
    labels = [r.dimension_name for r in results]
    negative = [1, 2]
    neutral = [3]
    positive = [4, 5]
    if results and len(results[0].item_columns) > 0:
        first_series = results[0].item_columns[0]
        if isinstance(first_series, pd.Series):
            n_points = infer_likert_points(first_series)
            if n_points == 7:
                negative = [1, 2, 3]
                positive = [5, 6, 7]
                neutral = [4]
            elif n_points == 6:
                negative = [1, 2]
                positive = [5, 6]
                neutral = [3, 4]

    neg_data = []
    neu_data = []
    pos_data = []

    for r in results:
        freq_table = r.item_statistics[0].get('frequency_table', {}) if r.item_statistics else {}
        total = sum(freq_table.values()) if freq_table else 1
        neg_pct = sum(freq_table.get(str(i), 0) for i in negative) / total * 100
        neu_pct = sum(freq_table.get(str(i), 0) for i in neutral) / total * 100
        pos_pct = sum(freq_table.get(str(i), 0) for i in positive) / total * 100
        neg_data.append(neg_pct)
        neu_data.append(neu_pct)
        pos_data.append(pos_pct)

    fig, ax = plt.subplots(figsize=(config.width, config.height), dpi=config.dpi)

    y = range(len(labels))
    height = 0.6

    ax.barh(y, neg_data, height=height, color=color_scheme[2], label='负向/不同意', edgecolor='white')
    ax.barh(y, neu_data, height=height, left=neg_data, color=color_scheme[1], label='中立', edgecolor='white')
    ax.barh(y, pos_data, height=height, left=[n + u for n, u in zip(neg_data, neu_data)],
            color=color_scheme[0], label='正向/同意', edgecolor='white')

    ax.set_yticks(y)
    ax.set_yticklabels(labels, fontsize=config.label_fontsize)
    ax.set_xlabel('百分比 (%)', fontsize=config.label_fontsize)
    ax.set_title(title, fontsize=config.title_fontsize, fontweight='bold', pad=15)
    ax.legend(loc='lower right', fontsize=config.legend_fontsize)
    ax.set_xlim(0, 100)
    ax.grid(axis='x', alpha=config.grid_alpha, linestyle='--')

    for i, (n, u, p) in enumerate(zip(neg_data, neu_data, pos_data)):
        if n > 5:
            ax.text(n / 2, i, f'{n:.0f}%', ha='center', va='center', fontsize=config.legend_fontsize, color='white')
        if u > 5:
            ax.text(n + u / 2, i, f'{u:.0f}%', ha='center', va='center', fontsize=config.legend_fontsize, color='white')
        if p > 5:
            ax.text(n + u + p / 2, i, f'{p:.0f}%', ha='center', va='center', fontsize=config.legend_fontsize, color='white')

    plt.tight_layout()
    plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return True


def plot_dimension_comparison(results: List[LikertScaleResult], title: str,
                               config: ChartConfig, output_path: str,
                               color_scheme: List[str]) -> bool:
    if not PLOTLIB_AVAILABLE or not results:
        return False

    labels = [r.dimension_name for r in results]
    means = [r.dimension_mean for r in results]
    stds = [r.dimension_std for r in results]

    fig, ax = plt.subplots(figsize=(config.width, config.height), dpi=config.dpi)

    colors_list = color_scheme[:len(labels)]
    colors_list = (colors_list * ((len(labels) // len(color_scheme)) + 1))[:len(labels)]

    bars = ax.bar(labels, means, color=colors_list, edgecolor='white', linewidth=2, width=0.6, yerr=stds, capsize=5)

    ax.set_ylabel('平均得分', fontsize=config.label_fontsize)
    ax.set_title(title, fontsize=config.title_fontsize, fontweight='bold', pad=15)
    ax.set_ylim(0, max(means + stds) * 1.2 if means else 5)
    ax.grid(axis='y', alpha=config.grid_alpha, linestyle='--')

    for bar in bars:
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, height + max(stds) * 0.2 if stds else height + 0.1,
                f'{height:.2f}', ha='center', va='bottom', fontsize=config.label_fontsize, fontweight='bold')

    plt.tight_layout()
    plt.savefig(output_path, dpi=config.dpi, bbox_inches='tight', facecolor='white')
    plt.close(fig)
    return True


class ChartGenerator:
    def __init__(self, output_dir: str = "charts", config: Optional[ChartConfig] = None,
                 color_scheme: str = "default"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = config or ChartConfig()
        self.color_scheme = CHART_COLORS.get(color_scheme, CHART_COLORS["default"])

    def generate_single_choice_charts(self, series: pd.Series, question_name: str,
                                       question_id: str) -> Tuple[Optional[str], Optional[str]]:
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', question_name)[:50]
        pie_path = str(self.output_dir / f"{question_id}_pie.png")
        bar_path = str(self.output_dir / f"{question_id}_bar.png")

        pie_ok = plot_single_choice_pie(series, question_name, self.config, pie_path, self.color_scheme)
        bar_ok = plot_single_choice_bar(series, question_name, self.config, bar_path, self.color_scheme)

        return (pie_path if pie_ok else None), (bar_path if bar_ok else None)

    def generate_multiple_choice_chart(self, series: pd.Series, question_name: str,
                                        question_id: str) -> Optional[str]:
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', question_name)[:50]
        chart_path = str(self.output_dir / f"{question_id}_multi.png")

        ok = plot_multiple_choice_bar(series, question_name, self.config, chart_path, self.color_scheme)
        return chart_path if ok else None

    def generate_likert_chart(self, series: pd.Series, question_name: str,
                              question_id: str) -> Optional[str]:
        safe_name = re.sub(r'[^\w\u4e00-\u9fff]', '_', question_name)[:50]
        chart_path = str(self.output_dir / f"{question_id}_likert.png")

        ok = plot_likert_histogram(series, question_name, self.config, chart_path, self.color_scheme)
        return chart_path if ok else None


class ComprehensiveAnalyzer:
    def __init__(self, data: pd.DataFrame, column_info: Dict[str, List[str]],
                 config: Optional[ChartConfig] = None, chart_output_dir: str = "charts"):
        self.data = data
        self.column_info = column_info
        self.config = config or ChartConfig()
        self.chart_generator = ChartGenerator(output_dir=chart_output_dir, config=self.config)
        self.answer_columns = column_info.get("answer_columns", [])
        self.metadata_columns = column_info.get("metadata_columns", [])

    def analyze_all_questions(self) -> Tuple[List[QuestionTypeResult], List[QuestionTypeResult], List[LikertScaleResult]]:
        single_choice_results = []
        multiple_choice_results = []
        likert_results = []

        for col in self.answer_columns:
            series = self.data[col]
            q_type = detect_question_type(series, col)

            freq, pct, cum_pct = calculate_frequency_stats(series)
            ct = calculate_central_tendency(series)
            disp = calculate_dispersion(series)
            valid = len(series.dropna())
            miss = len(series) - valid

            result = QuestionTypeResult(
                question_name=col,
                question_id=f"Q{self.answer_columns.index(col) + 1}",
                question_type=q_type,
                valid_responses=valid,
                missing_count=miss,
                missing_rate=round(miss / len(series), 4) if len(series) > 0 else 0,
                frequency_table=freq,
                percentage_table=pct,
                cumulative_table=cum_pct,
                central_tendency=ct,
                dispersion=disp,
            )

            if q_type == "single_choice":
                pie_path, bar_path = self.chart_generator.generate_single_choice_charts(series, col, result.question_id)
                result.chart_path = pie_path
                single_choice_results.append(result)

            elif q_type == "multiple_choice":
                chart_path = self.chart_generator.generate_multiple_choice_chart(series, col, result.question_id)
                result.chart_path = chart_path
                multiple_choice_results.append(result)

            elif q_type == "likert_scale":
                chart_path = self.chart_generator.generate_likert_chart(series, col, result.question_id)
                result.chart_path = chart_path
                likert_results.append(result)

            result.analysis_text = generate_analysis_text(result)

        return single_choice_results, multiple_choice_results, likert_results

    def generate_overall_analysis(self, single_results: List[QuestionTypeResult],
                                    multi_results: List[QuestionTypeResult],
                                    likert_results: List[QuestionTypeResult]) -> str:
        total_questions = len(single_results) + len(multi_results) + len(likert_results)

        if total_questions == 0:
            return "未检测到有效题目数据。"

        avg_missing_rate = 0.0
        if self.answer_columns:
            total_missing = sum(
                r.missing_rate for r in single_results + multi_results + likert_results
            )
            avg_missing_rate = total_missing / total_questions if total_questions > 0 else 0

        text = f"## 综合分析报告\n\n"
        text += f"本问卷共包含{total_questions}道有效题目，"
        text += f"其中单选题{len(single_results)}道，多选题{len(multi_results)}道，量表题{len(likert_results)}道。\n\n"

        text += f"### 一、数据质量概况\n\n"
        if avg_missing_rate < 0.05:
            text += f"问卷整体数据质量良好，各题缺失率平均为{avg_missing_rate:.1%}，"
            text += f"无回答误差控制在较低水平。\n\n"
        elif avg_missing_rate < 0.15:
            text += f"问卷存在一定比例的无回答情况，各题缺失率平均为{avg_missing_rate:.1%}，"
            text += f"建议关注缺失数据的成因。\n\n"
        else:
            text += f"问卷缺失率较高，各题缺失率平均为{avg_missing_rate:.1%}，"
            text += f"可能存在系统性无回答问题，需进一步调查原因。\n\n"

        if single_results:
            high_concentration = [r for r in single_results if r.percentage_table and max(r.percentage_table.values()) > 0.5]
            if high_concentration:
                text += f"单选题中，有{len(high_concentration)}道题选项分布高度集中（>50%选择同一选项），"
                text += f"表明这些题目可能存在趋同倾向。\n\n"

        if likert_results:
            positive_count = len([r for r in likert_results if r.central_tendency.get('mean', 0) >= 4])
            negative_count = len([r for r in likert_results if r.central_tendency.get('mean', 0) < 3])
            neutral_count = len(likert_results) - positive_count - negative_count

            text += f"### 二、量表题整体倾向\n\n"
            text += f"在{len(likert_results)}道量表题中：\n"
            text += f"- 正向倾向（均值≥4）：{positive_count}道（{positive_count/len(likert_results):.1%}）\n"
            text += f"- 中立倾向（3≤均值<4）：{neutral_count}道（{neutral_count/len(likert_results):.1%}）\n"
            text += f"- 负向倾向（均值<3）：{negative_count}道（{negative_count/len(likert_results):.1%}）\n\n"

            overall_mean = sum(r.central_tendency.get('mean', 0) for r in likert_results) / len(likert_results)
            overall_std = sum(r.dispersion.get('std', 0) for r in likert_results) / len(likert_results)
            text += f"量表整体均值为{overall_mean:.2f}，平均标准差为{overall_std:.2f}，"
            if overall_mean >= 4:
                text += f"反映出被调查者整体持正向态度。\n\n"
            elif overall_mean >= 3:
                text += f"反映出被调查者整体态度中立或模糊。\n\n"
            else:
                text += f"反映出被调查者整体持负向态度。\n\n"

        if multi_results:
            avg_selections = sum(sum(r.frequency_table.values()) / r.valid_responses for r in multi_results if r.valid_responses > 0)
            text += f"### 三、多选题分析\n\n"
            text += f"多选题人均选择数为{avg_selections:.1f}个，"
            text += f"表明被调查者在该类问题上参与度{'较高' if avg_selections >= 3 else '中等' if avg_selections >= 2 else '较低'}。\n\n"

        text += f"### 四、结论与建议\n\n"
        if avg_missing_rate < 0.1 and (not likert_results or sum(r.central_tendency.get('mean', 0) for r in likert_results) / len(likert_results) >= 3.5):
            text += f"本次调查数据质量较好，抽样结果具有较好的代表性，建议可用于后续正式分析。\n\n"
        elif avg_missing_rate < 0.2:
            text += f"本次调查数据质量基本合格，但需注意无回答可能带来的偏倚，"
            text += f"建议在分析时适当考虑加权调整。\n\n"
        else:
            text += f"本次调查数据质量问题较为突出，建议在解释结果时保持谨慎，"
            text += f"并考虑补充调查或调整抽样方案。\n\n"

        return text


class ReportExporter:
    def __init__(self, report: ComprehensiveReport, output_dir: str = "reports"):
        self.report = report
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_to_json(self, file_name: str = "comprehensive_report.json") -> Path:
        report_dict = {
            "report_title": self.report.report_title,
            "generated_at": self.report.generated_at,
            "data_source": self.report.data_source,
            "total_respondents": self.report.total_respondents,
            "valid_respondents": self.report.valid_respondents,
            "response_rate": self.report.response_rate,
            "single_choice_results": [
                {
                    "question_name": r.question_name,
                    "question_id": r.question_id,
                    "question_type": r.question_type,
                    "valid_responses": r.valid_responses,
                    "missing_count": r.missing_count,
                    "missing_rate": r.missing_rate,
                    "frequency_table": r.frequency_table,
                    "percentage_table": r.percentage_table,
                    "cumulative_table": r.cumulative_table,
                    "central_tendency": r.central_tendency,
                    "dispersion": r.dispersion,
                    "chart_path": r.chart_path,
                    "analysis_text": r.analysis_text,
                } for r in self.report.single_choice_results
            ],
            "multiple_choice_results": [
                {
                    "question_name": r.question_name,
                    "question_id": r.question_id,
                    "question_type": r.question_type,
                    "valid_responses": r.valid_responses,
                    "missing_count": r.missing_count,
                    "missing_rate": r.missing_rate,
                    "frequency_table": r.frequency_table,
                    "percentage_table": r.percentage_table,
                    "cumulative_table": r.cumulative_table,
                    "central_tendency": r.central_tendency,
                    "dispersion": r.dispersion,
                    "chart_path": r.chart_path,
                    "analysis_text": r.analysis_text,
                } for r in self.report.multiple_choice_results
            ],
            "likert_scale_results": [
                {
                    "dimension_name": r.dimension_name,
                    "item_columns": r.item_columns,
                    "dimension_mean": r.dimension_mean,
                    "dimension_std": r.dimension_std,
                    "dimension_variance": r.dimension_variance,
                    "dimension_median": r.dimension_median,
                    "dimension_min": r.dimension_min,
                    "dimension_max": r.dimension_max,
                    "dimension_range": r.dimension_range,
                    "cronbach_alpha": r.cronbach_alpha,
                    "item_statistics": r.item_statistics,
                    "chart_path": r.chart_path,
                    "analysis_text": r.analysis_text,
                } for r in self.report.likert_scale_results
            ],
            "overall_analysis": self.report.overall_analysis,
            "chart_output_dir": self.report.chart_output_dir,
            "data_summary": self.report.data_summary,
        }

        output_path = self.output_dir / file_name
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(report_dict, f, ensure_ascii=False, indent=2)
        return output_path

    def export_to_markdown(self, file_name: str = "comprehensive_report.md") -> Path:
        lines = []
        lines.append(f"# {self.report.report_title}\n")
        lines.append(f"**生成时间**: {self.report.generated_at}\n")
        lines.append(f"**数据来源**: {self.report.data_source}\n")
        lines.append(f"**样本信息**: 共{self.report.total_respondents}人，有效样本{self.report.valid_respondents}人，有效率{self.report.response_rate:.1%}\n")
        lines.append("---\n")

        if self.report.single_choice_results:
            lines.append("## 单选题分析\n\n")
            for r in self.report.single_choice_results:
                lines.append(f"### {r.question_id}. {r.question_name}\n")
                lines.append(f"**有效回答**: {r.valid_responses} | **缺失**: {r.missing_count}（{r.missing_rate:.1%}）\n\n")
                lines.append("| 选项 | 频数 | 百分比 | 累计百分比 |\n")
                lines.append("|------|------|--------|----------|\n")
                for opt, cnt in sorted(r.frequency_table.items(), key=lambda x: x[1], reverse=True):
                    pct = r.percentage_table.get(opt, 0)
                    cum = r.cumulative_table.get(opt, 0)
                    lines.append(f"| {opt} | {cnt} | {pct:.1%} | {cum:.1%} |\n")
                lines.append(f"\n**集中趋势**: 均值={r.central_tendency['mean']:.2f}, 中位数={r.central_tendency['median']:.2f}, 众数={r.central_tendency['mode']:.2f}\n")
                lines.append(f"**离散程度**: 标准差={r.dispersion['std']:.2f}, 方差={r.dispersion['variance']:.2f}, 极差={r.dispersion['range']:.2f}\n")
                if r.chart_path:
                    lines.append(f"\n![图表]({r.chart_path})\n")
                lines.append(f"\n**分析**: {r.analysis_text}\n")
                lines.append("---\n\n")

        if self.report.multiple_choice_results:
            lines.append("## 多选题分析\n\n")
            for r in self.report.multiple_choice_results:
                lines.append(f"### {r.question_id}. {r.question_name}\n")
                lines.append(f"**有效回答**: {r.valid_responses} | **总选择次数**: {sum(r.frequency_table.values())}\n\n")
                lines.append("| 选项 | 选择次数 | 百分比 |\n")
                lines.append("|------|----------|--------|\n")
                for opt, cnt in sorted(r.frequency_table.items(), key=lambda x: x[1], reverse=True):
                    pct = r.percentage_table.get(opt, 0)
                    lines.append(f"| {opt} | {cnt} | {pct:.1%} |\n")
                if r.chart_path:
                    lines.append(f"\n![图表]({r.chart_path})\n")
                lines.append(f"\n**分析**: {r.analysis_text}\n")
                lines.append("---\n\n")

        if self.report.likert_scale_results:
            lines.append("## 量表题分析\n\n")
            for r in self.report.likert_scale_results:
                lines.append(f"### {r.dimension_name}\n")
                lines.append(f"**均值**: {r.dimension_mean:.3f} | **标准差**: {r.dimension_std:.3f} | **克隆巴赫α**: {r.cronbach_alpha:.3f}\n\n")
                if r.item_statistics:
                    lines.append("| 题项 | 均值 | 标准差 | 删除后α |\n")
                    lines.append("|------|------|--------|--------|\n")
                    for item_stat in r.item_statistics:
                        lines.append(f"| {item_stat.get('question_name', 'N/A')} | {item_stat.get('mean', 0):.3f} | {item_stat.get('std', 0):.3f} | {item_stat.get('alpha_if_deleted', 'N/A')} |\n")
                if r.chart_path:
                    lines.append(f"\n![图表]({r.chart_path})\n")
                lines.append(f"\n**分析**: {r.analysis_text}\n")
                lines.append("---\n\n")

        lines.append("## 综合分析\n\n")
        lines.append(self.report.overall_analysis)

        output_path = self.output_dir / file_name
        output_path.write_text('\n'.join(lines), encoding='utf-8')
        return output_path

    def export_to_csv(self, file_name: str = "questionnaire_statistics.csv") -> Path:
        all_results = []

        for r in self.report.single_choice_results:
            all_results.append({
                "题号": r.question_id,
                "题名": r.question_name,
                "题型": "单选题",
                "有效回答": r.valid_responses,
                "缺失数": r.missing_count,
                "缺失率": r.missing_rate,
                "均值": r.central_tendency.get('mean', ''),
                "标准差": r.dispersion.get('std', ''),
                "中位数": r.central_tendency.get('median', ''),
                "最大值": r.dispersion.get('max', ''),
                "最小值": r.dispersion.get('min', ''),
            })

        for r in self.report.multiple_choice_results:
            all_results.append({
                "题号": r.question_id,
                "题名": r.question_name,
                "题型": "多选题",
                "有效回答": r.valid_responses,
                "缺失数": r.missing_count,
                "缺失率": r.missing_rate,
                "均值": '',
                "标准差": '',
                "中位数": '',
                "最大值": '',
                "最小值": '',
            })

        for r in self.report.likert_scale_results:
            all_results.append({
                "题号": r.dimension_name,
                "题名": "",
                "题型": "量表题",
                "有效回答": self.report.valid_respondents,
                "缺失数": self.report.total_respondents - self.report.valid_respondents,
                "缺失率": 1 - self.report.response_rate,
                "均值": r.dimension_mean,
                "标准差": r.dimension_std,
                "中位数": r.dimension_median,
                "最大值": r.dimension_max,
                "最小值": r.dimension_min,
            })

        df = pd.DataFrame(all_results)
        output_path = self.output_dir / file_name
        df.to_csv(output_path, index=False, encoding='utf-8-sig')
        return output_path

    def export_combined_excel(self, file_name: str = "comprehensive_report.xlsx") -> Path:
        output_path = self.output_dir / file_name
        with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
            summary_data = {
                "指标": ["报告标题", "生成时间", "数据来源", "总样本数", "有效样本数", "有效率"],
                "数值": [self.report.report_title, self.report.generated_at, self.report.data_source,
                        self.report.total_respondents, self.report.valid_respondents, f"{self.report.response_rate:.1%}"]
            }
            pd.DataFrame(summary_data).to_excel(writer, sheet_name="报告摘要", index=False)

            if self.report.single_choice_results:
                single_data = []
                for r in self.report.single_choice_results:
                    for opt, cnt in r.frequency_table.items():
                        single_data.append({
                            "题号": r.question_id,
                            "题名": r.question_name,
                            "选项": opt,
                            "频数": cnt,
                            "百分比": f"{r.percentage_table.get(opt, 0):.1%}",
                            "均值": r.central_tendency.get('mean', ''),
                            "标准差": r.dispersion.get('std', ''),
                        })
                pd.DataFrame(single_data).to_excel(writer, sheet_name="单选题", index=False)

            if self.report.multiple_choice_results:
                multi_data = []
                for r in self.report.multiple_choice_results:
                    for opt, cnt in r.frequency_table.items():
                        multi_data.append({
                            "题号": r.question_id,
                            "题名": r.question_name,
                            "选项": opt,
                            "选择次数": cnt,
                            "百分比": f"{r.percentage_table.get(opt, 0):.1%}",
                        })
                pd.DataFrame(multi_data).to_excel(writer, sheet_name="多选题", index=False)

            if self.report.likert_scale_results:
                likert_data = []
                for r in self.report.likert_scale_results:
                    likert_data.append({
                        "维度": r.dimension_name,
                        "均值": round(r.dimension_mean, 3),
                        "标准差": round(r.dimension_std, 3),
                        "方差": round(r.dimension_variance, 3),
                        "中位数": round(r.dimension_median, 3),
                        "最小值": round(r.dimension_min, 3),
                        "最大值": round(r.dimension_max, 3),
                        "克隆巴赫α": round(r.cronbach_alpha, 3),
                    })
                pd.DataFrame(likert_data).to_excel(writer, sheet_name="量表维度", index=False)

            all_stats = []
            for r in self.report.single_choice_results:
                all_stats.append({
                    "题号": r.question_id,
                    "题名": r.question_name,
                    "题型": "单选题",
                    "有效回答": r.valid_responses,
                    "缺失率": f"{r.missing_rate:.1%}",
                    "均值": round(r.central_tendency.get('mean', 0), 3),
                    "标准差": round(r.dispersion.get('std', 0), 3),
                })
            for r in self.report.multiple_choice_results:
                all_stats.append({
                    "题号": r.question_id,
                    "题名": r.question_name,
                    "题型": "多选题",
                    "有效回答": r.valid_responses,
                    "缺失率": f"{r.missing_rate:.1%}",
                    "均值": "-",
                    "标准差": "-",
                })
            for r in self.report.likert_scale_results:
                all_stats.append({
                    "题号": "-",
                    "题名": r.dimension_name,
                    "题型": "量表题",
                    "有效回答": self.report.valid_respondents,
                    "缺失率": f"{1-self.report.response_rate:.1%}",
                    "均值": round(r.dimension_mean, 3),
                    "标准差": round(r.dimension_std, 3),
                })
            pd.DataFrame(all_stats).to_excel(writer, sheet_name="全部统计汇总", index=False)

        return output_path

    def export_all_formats(self) -> Dict[str, Path]:
        results = {}
        try:
            results["json"] = self.export_to_json()
        except Exception as e:
            results["json"] = None
            print(f"JSON导出失败: {e}")

        try:
            results["markdown"] = self.export_to_markdown()
        except Exception as e:
            results["markdown"] = None
            print(f"Markdown导出失败: {e}")

        try:
            results["csv"] = self.export_to_csv()
        except Exception as e:
            results["csv"] = None
            print(f"CSV导出失败: {e}")

        try:
            results["excel"] = self.export_combined_excel()
        except Exception as e:
            results["excel"] = None
            print(f"Excel导出失败: {e}")

        return {k: v for k, v in results.items() if v is not None}


def integrate_all_modules(data: pd.DataFrame, column_info: Dict[str, List[str]],
                          screening_result: Any = None, output_dir: str = "integrated_output") -> ComprehensiveReport:
    chart_output = str(Path(output_dir) / "charts")
    Path(chart_output).mkdir(parents=True, exist_ok=True)

    config = ChartConfig(
        width=12,
        height=7,
        dpi=150,
        title_fontsize=14,
        label_fontsize=10,
        legend_fontsize=9,
        max_categories=8,
        color_scheme="professional"
    )

    analyzer = ComprehensiveAnalyzer(
        data=data,
        column_info=column_info,
        config=config,
        chart_output_dir=chart_output
    )

    single_results, multi_results, likert_results = analyzer.analyze_all_questions()

    overall_analysis = analyzer.generate_overall_analysis(single_results, multi_results, likert_results)

    total = len(data)
    valid_n = total
    if screening_result:
        valid_n = getattr(screening_result, 'valid_rows', total)

    report = ComprehensiveReport(
        report_title="问卷综合分析报告",
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        data_source="问卷星数据",
        total_respondents=total,
        valid_respondents=valid_n,
        response_rate=valid_n / total if total > 0 else 0,
        single_choice_results=single_results,
        multiple_choice_results=multi_results,
        likert_scale_results=likert_results,
        overall_analysis=overall_analysis,
        chart_output_dir=chart_output,
        data_summary={
            "total_questions": len(single_results) + len(multi_results) + len(likert_results),
            "single_choice_count": len(single_results),
            "multiple_choice_count": len(multi_results),
            "likert_scale_count": len(likert_results),
            "avg_missing_rate": sum(r.missing_rate for r in single_results + multi_results + likert_results) /
                                max(len(single_results) + len(multi_results) + len(likert_results), 1),
        }
    )

    return report


def main():
    import argparse
    parser = argparse.ArgumentParser(description="综合报告生成系统")
    parser.add_argument("input_file", nargs="?", help="输入问卷数据文件（CSV/Excel）")
    parser.add_argument("-o", "--output-dir", default="integrated_output", help="输出目录")
    parser.add_argument("--chart-dpi", type=int, default=150, help="图表分辨率")
    parser.add_argument("--color-scheme", default="professional",
                        choices=["default", "professional", "warm", "cool", "pastel"],
                        help="配色方案")
    args = parser.parse_args()

    if not args.input_file:
        print("请提供输入文件路径")
        print("用法: python integrated_reporting_system.py <问卷数据文件> [-o 输出目录]")
        return

    input_path = Path(args.input_file)
    if not input_path.exists():
        print(f"文件不存在: {input_path}")
        return

    print(f"正在读取数据: {input_path}")
    if input_path.suffix.lower() == '.csv':
        try:
            data = pd.read_csv(input_path, encoding='utf-8-sig')
        except:
            data = pd.read_csv(input_path, encoding='gbk')
    else:
        data = pd.read_excel(input_path)

    print(f"数据加载完成: {data.shape[0]}行 x {data.shape[1]}列")

    from group2_invalid_questionnaire_screening1 import (
        normalize_dataframe, infer_columns, screen_questionnaires,
        ScreeningConfig
    )

    print("正在标准化数据...")
    standard_df = normalize_dataframe(data)
    column_info = infer_columns(standard_df)

    print("正在筛查无效问卷...")
    screening_config = ScreeningConfig()
    valid_df, invalid_df, log_df, screening_result, context = screen_questionnaires(
        standard_df, config=screening_config, column_info=column_info
    )

    print("正在生成综合分析报告...")
    report = integrate_all_modules(
        data=valid_df,
        column_info=column_info,
        screening_result=screening_result,
        output_dir=args.output_dir
    )

    print("正在导出报告...")
    exporter = ReportExporter(report, output_dir=args.output_dir)
    export_results = exporter.export_all_formats()

    print("\n" + "=" * 60)
    print("报告生成完成!")
    print("=" * 60)
    print(f"\n输出目录: {args.output_dir}")
    print(f"\n生成的文件:")
    for fmt, path in export_results.items():
        print(f"  - {fmt.upper()}: {path}")
    print(f"\n图表目录: {report.chart_output_dir}")


if __name__ == "__main__":
    main()
