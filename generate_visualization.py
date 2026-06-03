# -*- coding: utf-8 -*-
"""
项目可视化大纲生成脚本
生成系统架构图、模块关系图、数据流图等可视化内容
"""

from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
import numpy as np

plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False

output_dir = Path("可视化大纲")
output_dir.mkdir(parents=True, exist_ok=True)


def draw_system_architecture():
    fig, ax = plt.subplots(figsize=(16, 12), dpi=150)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 12)
    ax.axis('off')
    ax.set_title('问卷数据一体化处理系统架构图', fontsize=20, fontweight='bold', pad=20)

    colors = {
        'presentation': '#3498DB',
        'business': '#27AE60',
        'data': '#E74C3C',
        'infrastructure': '#9B59B6',
        'module': '#F39C12',
    }

    layers = [
        (1, 10, 14, 1.5, '表现层 (Presentation Layer)', colors['presentation']),
        (1, 7.5, 14, 2, '业务层 (Business Layer)', colors['business']),
        (1, 4.5, 14, 2, '数据层 (Data Layer)', colors['data']),
        (1, 1.5, 14, 2, '基础层 (Infrastructure Layer)', colors['infrastructure']),
    ]

    for x, y, w, h, label, color in layers:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                               facecolor=color, alpha=0.3, edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x + 0.3, y + h - 0.3, label, fontsize=12, fontweight='bold', color=color)

    presentation_modules = [
        (2, 10.3, 3, 0.8, 'Streamlit\nWeb界面'),
        (6, 10.3, 3, 0.8, '命令行\nCLI接口'),
        (10, 10.3, 3, 0.8, 'API\n编程接口'),
    ]

    business_modules = [
        (1.5, 8.2, 2.5, 1, '样本量\n计算模块'),
        (4.5, 8.2, 2.5, 1, '无效问卷\n筛查模块'),
        (7.5, 8.2, 2.5, 1, '量表信度\n分析模块'),
        (10.5, 8.2, 2.5, 1, '综合报告\n生成模块'),
    ]

    data_modules = [
        (1.5, 5.2, 3, 1, '数据接入\n(load_data)'),
        (5.5, 5.2, 3, 1, '标准化处理\n(normalize)'),
        (9.5, 5.2, 3, 1, '结果导出\n(export)'),
    ]

    infra_modules = [
        (2, 2, 2.5, 1, 'Pandas\n数据处理'),
        (5, 2, 2.5, 1, 'NumPy\n数值计算'),
        (8, 2, 2.5, 1, 'Matplotlib\n可视化'),
        (11, 2, 2.5, 1, 'Requests\n网络请求'),
    ]

    all_modules = presentation_modules + business_modules + data_modules + infra_modules

    for x, y, w, h, label in all_modules:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02",
                               facecolor='white', edgecolor='#2C3E50', linewidth=1.5)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, fontsize=9, ha='center', va='center',
                fontweight='bold', color='#2C3E50')

    arrows = [
        (5, 10.3, 5, 9.5),
        (7.5, 8.2, 7.5, 7.5),
        (7.5, 5.2, 7.5, 4.5),
    ]

    for x1, y1, x2, y2 in arrows:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#7F8C8D', lw=2))

    plt.tight_layout()
    plt.savefig(output_dir / '系统架构图.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print("✅ 系统架构图已生成")


def draw_module_relation():
    fig, ax = plt.subplots(figsize=(14, 10), dpi=150)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('五人模块协作关系图', fontsize=18, fontweight='bold', pad=20)

    modules = [
        (2, 7, 3, 1.5, '组员1\n数据接入与标准化', '#3498DB'),
        (6, 7, 3, 1.5, '组员2\n无效问卷筛查', '#E74C3C'),
        (10, 7, 3, 1.5, '组员3\n样本量计算', '#27AE60'),
        (4, 3.5, 3, 1.5, '组员4\n量表信度分析', '#9B59B6'),
        (8, 3.5, 3, 1.5, '组员5\n综合报告生成', '#F39C12'),
    ]

    for x, y, w, h, label, color in modules:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                               facecolor=color, alpha=0.7, edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, fontsize=11, ha='center', va='center',
                fontweight='bold', color='white')

    connections = [
        ((5, 7.75), (6, 7.75), '标准化数据'),
        ((9, 7.75), (10, 7.75), '筛查结果'),
        ((3.5, 7), (5.5, 5), '有效样本'),
        ((11.5, 7), (9.5, 5), '样本量信息'),
        ((7, 3.5), (8, 3.5), '信度结果'),
        ((7.5, 5), (9.5, 5), '统计数据'),
    ]

    for (x1, y1), (x2, y2), label in connections:
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                    arrowprops=dict(arrowstyle='->', color='#7F8C8D', lw=2,
                                    connectionstyle="arc3,rad=0.1"))
        mid_x, mid_y = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mid_x, mid_y + 0.3, label, fontsize=8, ha='center', color='#7F8C8D',
                bbox=dict(boxstyle='round', facecolor='white', alpha=0.8))

    plt.tight_layout()
    plt.savefig(output_dir / '模块协作关系图.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print("✅ 模块协作关系图已生成")


def draw_data_flow():
    fig, ax = plt.subplots(figsize=(16, 8), dpi=150)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 8)
    ax.axis('off')
    ax.set_title('数据处理流程图', fontsize=18, fontweight='bold', pad=20)

    steps = [
        (1, 4, 2, 2, '原始数据\n(Raw Data)', '#E74C3C', 'Excel/CSV'),
        (4, 4, 2, 2, '数据接入\n(M1)', '#3498DB', '读取+识别'),
        (7, 4, 2, 2, '标准化\n(M1)', '#3498DB', '列名+空值'),
        (10, 4, 2, 2, '无效筛查\n(M2)', '#E74C3C', '四维判定'),
        (13, 4, 2, 2, '有效样本\n(Valid)', '#27AE60', '清洗数据'),
    ]

    for x, y, w, h, label, color, desc in steps:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                               facecolor=color, alpha=0.7, edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2 + 0.3, label, fontsize=10, ha='center', va='center',
                fontweight='bold', color='white')
        ax.text(x + w/2, y + 0.3, desc, fontsize=8, ha='center', va='center', color='#2C3E50')

    for i in range(len(steps) - 1):
        x1 = steps[i][0] + steps[i][2]
        x2 = steps[i+1][0]
        y = steps[i][1] + steps[i][3] / 2
        ax.annotate('', xy=(x2, y), xytext=(x1, y),
                    arrowprops=dict(arrowstyle='->', color='#2C3E50', lw=2))

    analysis_steps = [
        (5.5, 1, 2, 1.5, '样本量计算\n(M3)', '#27AE60'),
        (8.5, 1, 2, 1.5, '量表分析\n(M4)', '#9B59B6'),
        (11.5, 1, 2, 1.5, '报告生成\n(M5)', '#F39C12'),
    ]

    for x, y, w, h, label, color in analysis_steps:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                               facecolor=color, alpha=0.7, edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h/2, label, fontsize=9, ha='center', va='center',
                fontweight='bold', color='white')

    ax.annotate('', xy=(11, 4), xytext=(12.5, 2.5),
                arrowprops=dict(arrowstyle='->', color='#7F8C8D', lw=1.5,
                                connectionstyle="arc3,rad=0.3"))

    plt.tight_layout()
    plt.savefig(output_dir / '数据流程图.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print("✅ 数据流程图已生成")


def draw_screening_indicators():
    fig, ax = plt.subplots(figsize=(12, 10), dpi=150)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('无效问卷筛查四维指标体系', fontsize=18, fontweight='bold', pad=20)

    center_x, center_y = 6, 5
    center_rect = FancyBboxPatch((center_x - 1.5, center_y - 1), 3, 2,
                                  boxstyle="round,pad=0.05",
                                  facecolor='#2C3E50', alpha=0.9,
                                  edgecolor='#2C3E50', linewidth=2)
    ax.add_patch(center_rect)
    ax.text(center_x, center_y, '无效问卷\n判定', fontsize=12, ha='center', va='center',
            fontweight='bold', color='white')

    indicators = [
        (2, 8, '时间维度', '作答时长 < 题目数×2秒\n或 < 45秒', '#E74C3C'),
        (10, 8, '完整维度', '缺答率 ≥ 40%\n大面积空白', '#3498DB'),
        (2, 2, '一致性维度', '统一答案 或\n同选项占比≥90%', '#27AE60'),
        (10, 2, '内容维度', '无意义乱填占比 ≥ 60%\n如"aaaa"、"123"', '#9B59B6'),
    ]

    for x, y, title, desc, color in indicators:
        rect = FancyBboxPatch((x - 1.5, y - 1.2), 3, 2.4,
                               boxstyle="round,pad=0.05",
                               facecolor=color, alpha=0.7,
                               edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y + 0.5, title, fontsize=11, ha='center', va='center',
                fontweight='bold', color='white')
        ax.text(x, y - 0.5, desc, fontsize=8, ha='center', va='center', color='white')

        arrow_x = center_x + (x - center_x) * 0.5
        arrow_y = center_y + (y - center_y) * 0.5
        ax.annotate('', xy=(arrow_x, arrow_y), xytext=(center_x, center_y),
                    arrowprops=dict(arrowstyle='->', color='#7F8C8D', lw=2))

    plt.tight_layout()
    plt.savefig(output_dir / '筛查指标体系图.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print("✅ 筛查指标体系图已生成")


def draw_innovation_points():
    fig, ax = plt.subplots(figsize=(14, 10), dpi=150)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 10)
    ax.axis('off')
    ax.set_title('系统五大创新点', fontsize=18, fontweight='bold', pad=20)

    innovations = [
        (2, 7.5, '创新点一', '智能题型识别', '自动识别单选/多选/量表\n无需人工标注', '#E74C3C'),
        (7.5, 7.5, '创新点二', '多维无效筛查', '四维指标体系量化判定\n可复现、可解释', '#3498DB'),
        (12, 7.5, '创新点三', '自适应样本计算', '无限/有限总体自动切换\n含无效缓冲设计', '#27AE60'),
        (4.5, 3.5, '创新点四', '批量图表+文案', '图表样式自适应\n分析文字自动生成', '#9B59B6'),
        (9.5, 3.5, '创新点五', 'AI辅助分析', '支持多平台大模型\n人机协作新模式', '#F39C12'),
    ]

    for x, y, num, title, desc, color in innovations:
        circle = plt.Circle((x, y), 1.2, facecolor=color, alpha=0.7, edgecolor=color, linewidth=2)
        ax.add_patch(circle)
        ax.text(x, y + 0.3, num, fontsize=10, ha='center', va='center',
                fontweight='bold', color='white')
        ax.text(x, y - 0.3, '⭐', fontsize=14, ha='center', va='center', color='white')

        rect = FancyBboxPatch((x - 2, y - 3), 4, 1.5,
                               boxstyle="round,pad=0.05",
                               facecolor='white', edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y - 2.25, title, fontsize=10, ha='center', va='center',
                fontweight='bold', color=color)
        ax.text(x, y - 3.5, desc, fontsize=8, ha='center', va='center', color='#2C3E50')

    plt.tight_layout()
    plt.savefig(output_dir / '创新点总览图.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print("✅ 创新点总览图已生成")


def draw_output_structure():
    fig, ax = plt.subplots(figsize=(14, 8), dpi=150)
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 8)
    ax.axis('off')
    ax.set_title('系统输出文件结构', fontsize=18, fontweight='bold', pad=20)

    categories = [
        (1.5, 5, 2.5, 2.5, '数据文件', [
            'standard_data.csv',
            'cleaned_data.csv',
            'invalid_data.csv'
        ], '#3498DB'),
        (5, 5, 2.5, 2.5, '日志文件', [
            'filter_log.csv',
            'error_report.csv',
            'run_log.txt'
        ], '#E74C3C'),
        (8.5, 5, 2.5, 2.5, '图表文件', [
            'Q1_pie.png',
            'Q1_bar.png',
            'Q2_likert.png'
        ], '#27AE60'),
        (12, 5, 2.5, 2.5, '报告文件', [
            'report.md',
            'report.json',
            'report.xlsx'
        ], '#9B59B6'),
    ]

    for x, y, w, h, title, files, color in categories:
        rect = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                               facecolor=color, alpha=0.3, edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x + w/2, y + h - 0.4, title, fontsize=10, ha='center', va='center',
                fontweight='bold', color=color)

        for i, file in enumerate(files):
            ax.text(x + w/2, y + h - 1 - i * 0.6, file, fontsize=8, ha='center', va='center',
                    color='#2C3E50')

    output_dir_rect = FancyBboxPatch((1, 1), 12, 2.5, boxstyle="round,pad=0.05",
                                      facecolor='#F5F5F5', edgecolor='#2C3E50', linewidth=2)
    ax.add_patch(output_dir_rect)
    ax.text(7, 3, '输出目录 (output/)', fontsize=12, ha='center', va='center',
            fontweight='bold', color='#2C3E50')
    ax.text(7, 2, '包含：数据 + 日志 + 图表 + 报告 + 配置', fontsize=10, ha='center', va='center',
            color='#7F8C8D')

    plt.tight_layout()
    plt.savefig(output_dir / '输出文件结构图.png', dpi=150, bbox_inches='tight', facecolor='white')
    plt.close()
    print("✅ 输出文件结构图已生成")


def main():
    print("=" * 60)
    print("项目可视化大纲生成")
    print("=" * 60)

    draw_system_architecture()
    draw_module_relation()
    draw_data_flow()
    draw_screening_indicators()
    draw_innovation_points()
    draw_output_structure()

    print("\n" + "=" * 60)
    print(f"✅ 所有可视化图表已生成到: {output_dir.resolve()}")
    print("=" * 60)
    print("\n生成的文件列表：")
    for f in sorted(output_dir.glob("*.png")):
        print(f"  - {f.name}")


if __name__ == "__main__":
    main()
