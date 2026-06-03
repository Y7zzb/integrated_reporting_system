# -*- coding: utf-8 -*-
"""
AI 接口客户端模块
作用：把问卷星统计量摘要发送给 DeepSeek / 通义千问 / 豆包 / 自定义 OpenAI 兼容接口，
让 AI 根据已经计算好的统计量生成文字理解型分析报告。

注意：
1. 本模块不内置 API Key，需要运行时由用户自己填写。
2. AI 只负责“解释统计结果”，统计量由本地 Python 先计算，避免 AI 乱算。
3. 支持 OpenAI 兼容格式：POST {base_url}/chat/completions
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import requests


PROVIDER_PRESETS: Dict[str, Dict[str, str]] = {
    "DeepSeek": {
        "base_url": "https://api.deepseek.com",
        "model": "deepseek-chat",
    },
    "通义千问（阿里百炼）": {
        "base_url": "https://dashscope-intl.aliyuncs.com/compatible-mode/v1",
        "model": "qwen-plus",
    },
    "豆包（火山方舟 / OpenAI兼容）": {
        "base_url": "https://ark.cn-beijing.volces.com/api/v3",
        "model": "请填写你在火山方舟开通的模型名",
    },
    "自定义 OpenAI 兼容接口": {
        "base_url": "https://api.openai.com/v1",
        "model": "请填写模型名",
    },
}


def normalize_base_url(base_url: str) -> str:
    """规范化 Base URL，避免重复拼接 /chat/completions。"""
    base_url = (base_url or "").strip().rstrip("/")
    if base_url.endswith("/chat/completions"):
        base_url = base_url[: -len("/chat/completions")]
    return base_url


def build_headers(api_key: str) -> Dict[str, str]:
    """构造请求头。"""
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key.strip()}",
    }


def call_openai_compatible_chat(
    base_url: str,
    api_key: str,
    model: str,
    messages: List[Dict[str, str]],
    temperature: float = 0.25,
    max_tokens: int = 1600,
    timeout: int = 120,
) -> Tuple[str, Optional[dict]]:
    """
    调用 OpenAI 兼容的 chat/completions 接口。
    返回：AI 文本内容、原始 JSON 响应。
    """
    base_url = normalize_base_url(base_url)
    if not base_url:
        raise ValueError("Base URL 不能为空。")
    if not api_key:
        raise ValueError("API Key 不能为空。")
    if not model:
        raise ValueError("模型名称不能为空。")

    endpoint = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    response = requests.post(endpoint, headers=build_headers(api_key), json=payload, timeout=timeout)
    if response.status_code >= 400:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise RuntimeError(f"AI 接口调用失败：HTTP {response.status_code}，详情：{detail}")

    data = response.json()
    try:
        content = data["choices"][0]["message"].get("content", "")
    except Exception as exc:
        raise RuntimeError(f"AI 响应格式无法解析：{data}") from exc
    return content, data


def build_report_messages(statistical_context: str, user_requirement: str = "") -> List[Dict[str, str]]:
    """
    构造“自动统计报告”提示词。
    """
    system_prompt = """
你是一个抽样技术课程项目中的问卷数据统计分析助手。
你的任务不是重新计算数据，而是基于用户提供的 Python 统计量摘要，生成严谨、清晰、可直接放入报告的中文分析文字。
要求：
1. 必须围绕已经给出的样本量、缺失、频数、均值、标准差、量表均值、相关系数等统计量分析。
2. 不要编造统计量；没有出现的数据不要自己添加。
3. 文字要体现抽样技术课程相关表达，如样本结构、数据质量、非抽样误差、无回答情况、描述性统计、量表倾向等。
4. 结论要适合课程作业，不要写成商业咨询报告。
5. 输出结构建议包括：数据概况、数据质量、单选/多选分布、量表题分析、综合结论、后续分析建议。
"""
    user_prompt = f"""
以下是系统自动计算得到的问卷星数据统计量摘要，请你据此生成“文字理解型统计分析报告”。

【用户补充要求】
{user_requirement or "无"}

【统计量摘要】
{statistical_context}
"""
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_prompt.strip()},
    ]


def build_question_messages(statistical_context: str, question: str) -> List[Dict[str, str]]:
    """
    构造“针对统计结果进行自然语言问答”的提示词。
    """
    system_prompt = """
你是问卷星数据分析系统的 AI 统计解释模块。
你只能根据用户提供的统计量摘要回答问题，不能凭空编造没有出现的数据。
回答应简明、具体，并解释相关统计指标的含义。
"""
    user_prompt = f"""
【统计量摘要】
{statistical_context}

【用户问题】
{question}
"""
    return [
        {"role": "system", "content": system_prompt.strip()},
        {"role": "user", "content": user_prompt.strip()},
    ]
