# -*- coding: utf-8 -*-
"""
系统集成测试脚本
验证所有模块的兼容性和功能完整性
"""

import sys
from pathlib import Path

WORKSPACE_DIR = Path(r"C:\Users\派大星\PyCharmMiscProject")
for p in (WORKSPACE_DIR,):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import pandas as pd
import numpy as np


def test_imports():
    print("=" * 60)
    print("测试1: 模块导入测试")
    print("=" * 60)

    modules_to_test = [
        ("ai_client", "AI接口客户端"),
        ("group2_invalid_questionnaire_screening", "无效问卷筛查v1"),
        ("group2_invalid_questionnaire_screening1", "无效问卷筛查v2"),
        ("questionnaire_platform_core", "问卷平台核心"),
    ]

    results = {}
    for module_name, description in modules_to_test:
        try:
            module = __import__(module_name)
            print(f"✅ {description} ({module_name}) - 导入成功")
            results[module_name] = True
        except Exception as e:
            print(f"❌ {description} ({module_name}) - 导入失败: {e}")
            results[module_name] = False

    try:
        from integrated_reporting_system import (
            ComprehensiveAnalyzer,
            ReportExporter,
            ChartGenerator,
            ChartConfig,
            detect_question_type,
            calculate_frequency_stats,
            generate_analysis_text,
            ComprehensiveReport,
        )
        print(f"✅ 综合报告系统 - 导入成功")
        results["integrated_reporting_system"] = True
    except Exception as e:
        print(f"❌ 综合报告系统 - 导入失败: {e}")
        results["integrated_reporting_system"] = False

    return all(results.values())


def test_chart_generator():
    print("\n" + "=" * 60)
    print("测试2: 图表生成器测试")
    print("=" * 60)

    try:
        from integrated_reporting_system import ChartGenerator, ChartConfig

        config = ChartConfig(width=10, height=6, dpi=100)
        generator = ChartGenerator(output_dir="test_charts", config=config)

        test_data = pd.Series(np.random.choice([1, 2, 3, 4, 5], 100))
        pie_path, bar_path = generator.generate_single_choice_charts(
            test_data, "测试题目", "Q1"
        )

        if pie_path and bar_path:
            print(f"✅ 单选题图表生成成功: {pie_path}, {bar_path}")
        else:
            print(f"⚠️ 部分图表生成失败")

        multi_data = pd.Series(['A,B', 'B,C', 'A,C,D', 'A,B'] * 25)
        multi_path = generator.generate_multiple_choice_chart(
            multi_data, "测试多选题", "Q2"
        )
        if multi_path:
            print(f"✅ 多选题图表生成成功: {multi_path}")
        else:
            print(f"⚠️ 多选题图表生成失败")

        likert_data = pd.Series(np.random.choice([1, 2, 3, 4, 5], 100))
        likert_path = generator.generate_likert_chart(
            likert_data, "测试量表题", "Q3"
        )
        if likert_path:
            print(f"✅ 量表题图表生成成功: {likert_path}")
        else:
            print(f"⚠️ 量表题图表生成失败")

        import shutil
        shutil.rmtree("test_charts", ignore_errors=True)
        print("✅ 测试图表目录已清理")

        return True
    except Exception as e:
        print(f"❌ 图表生成测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_data_processing():
    print("\n" + "=" * 60)
    print("测试3: 数据处理流程测试")
    print("=" * 60)

    try:
        from group2_invalid_questionnaire_screening1 import (
            normalize_dataframe, infer_columns, screen_questionnaires,
            ScreeningConfig
        )

        test_data = pd.DataFrame({
            '答卷编号': range(1, 101),
            '提交时间': pd.date_range('2024-01-01', periods=100),
            '所用时间': ['60秒'] * 50 + ['30秒'] * 30 + ['90秒'] * 20,
            'Q1_您的性别': np.random.choice(['男', '女'], 100),
            'Q2_年龄阶段': np.random.choice(['18-25', '26-35', '36-45'], 100),
            'Q3_满意度': np.random.choice([1, 2, 3, 4, 5], 100),
            'Q4_可多选': np.random.choice(['A,B', 'A,C', 'B,C', 'A,B,C'], 100),
        })

        standard_df = normalize_dataframe(test_data)
        print(f"✅ 数据标准化完成: {standard_df.shape}")

        column_info = infer_columns(standard_df)
        print(f"✅ 字段识别完成:")
        print(f"   元信息列: {column_info['metadata_columns']}")
        print(f"   题目列: {column_info['answer_columns']}")

        config = ScreeningConfig()
        valid_df, invalid_df, log_df, result, context = screen_questionnaires(
            standard_df, config=config, column_info=column_info
        )

        print(f"✅ 无效筛查完成:")
        print(f"   总问卷: {result.total_rows}")
        print(f"   有效问卷: {result.valid_rows}")
        print(f"   无效问卷: {result.invalid_rows}")
        print(f"   有效率: {result.valid_rate:.1%}")

        return True
    except Exception as e:
        print(f"❌ 数据处理测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_comprehensive_analyzer():
    print("\n" + "=" * 60)
    print("测试4: 综合分析器测试")
    print("=" * 60)

    try:
        from integrated_reporting_system import (
            ComprehensiveAnalyzer,
            ReportExporter,
            ChartConfig,
            ComprehensiveReport,
            integrate_all_modules,
        )
        from group2_invalid_questionnaire_screening1 import (
            normalize_dataframe, infer_columns, screen_questionnaires,
            ScreeningConfig
        )

        test_data = pd.DataFrame({
            '答卷编号': range(1, 51),
            '提交时间': pd.date_range('2024-01-01', periods=50),
            'Q1_性别': np.random.choice(['男', '女'], 50),
            'Q2_年龄段': np.random.choice(['青年', '中年', '老年'], 50),
            'Q3_满意度': np.random.choice([1, 2, 3, 4, 5], 50),
            'Q4_可多选': np.random.choice(['A,B', 'A,C', 'B,C'], 50),
            'Q5_服务态度': np.random.choice([1, 2, 3, 4, 5], 50),
        })

        standard_df = normalize_dataframe(test_data)
        column_info = infer_columns(standard_df)

        config = ScreeningConfig()
        valid_df, invalid_df, log_df, result, context = screen_questionnaires(
            standard_df, config=config, column_info=column_info
        )

        chart_config = ChartConfig(width=10, height=6, dpi=100)

        analyzer = ComprehensiveAnalyzer(
            data=valid_df,
            column_info=column_info,
            config=chart_config,
            chart_output_dir="test_output/charts"
        )

        single_results, multi_results, likert_results = analyzer.analyze_all_questions()

        print(f"✅ 综合分析完成:")
        print(f"   单选题: {len(single_results)}道")
        print(f"   多选题: {len(multi_results)}道")
        print(f"   量表题: {len(likert_results)}道")

        for r in single_results:
            print(f"   - {r.question_id}: {r.question_name} ({r.question_type})")

        report = ComprehensiveReport(
            report_title="测试报告",
            generated_at="2024-01-01 12:00:00",
            data_source="测试数据",
            total_respondents=len(test_data),
            valid_respondents=len(valid_df),
            response_rate=len(valid_df) / len(test_data),
            single_choice_results=single_results,
            multiple_choice_results=multi_results,
            likert_scale_results=likert_results,
            overall_analysis="测试整体分析",
            chart_output_dir="test_output/charts",
        )

        exporter = ReportExporter(report, output_dir="test_output")
        export_results = exporter.export_all_formats()

        print(f"✅ 报告导出完成:")
        for fmt, path in export_results.items():
            if path:
                print(f"   - {fmt.upper()}: {path}")

        import shutil
        shutil.rmtree("test_output", ignore_errors=True)
        print("✅ 测试输出目录已清理")

        return True
    except Exception as e:
        print(f"❌ 综合分析测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_sample_calculation():
    print("\n" + "=" * 60)
    print("测试5: 样本量计算测试")
    print("=" * 60)

    try:
        from questionnaire_platform_core import calculate_sample

        test_cases = [
            {"confidence": 0.95, "margin_error": 0.05, "p": 0.5, "population": 10000, "actual_sample": 0},
            {"confidence": 0.95, "margin_error": 0.03, "p": 0.5, "population": 5000, "actual_sample": 400},
            {"confidence": 0.99, "margin_error": 0.05, "p": 0.5, "population": 20000, "actual_sample": 500},
        ]

        all_passed = True
        for i, params in enumerate(test_cases):
            result = calculate_sample(**params)
            print(f"测试用例{i+1}:")
            print(f"  参数: 置信度={params['confidence']}, 误差={params['margin_error']}, 总体={params['population']}")
            print(f"  结果: 最小样本={result['min_sample']}, 建议={result['suggested']}")
            if result['is_sufficient'] is not None:
                print(f"  样本充足: {result['is_sufficient']}")

        print("✅ 样本量计算测试完成")
        return all_passed
    except Exception as e:
        print(f"❌ 样本量计算测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("\n" + "=" * 60)
    print("问卷数据一体化处理系统 - 集成测试")
    print("=" * 60)

    results = {}

    results["imports"] = test_imports()
    results["charts"] = test_chart_generator()
    results["data_processing"] = test_data_processing()
    results["comprehensive"] = test_comprehensive_analyzer()
    results["sample_calculation"] = test_sample_calculation()

    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)

    for test_name, passed in results.items():
        status = "✅ 通过" if passed else "❌ 失败"
        print(f"  {test_name}: {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 60)
    if all_passed:
        print("🎉 所有测试通过！系统可以正常运行")
    else:
        print("⚠️ 部分测试失败，请检查错误信息")
    print("=" * 60)

    return all_passed


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
