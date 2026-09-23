"""DeepSeek（OpenAI 兼容接口）客户端。"""
import json
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from config import (
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    LLM_MAX_RETRIES, LLM_TIMEOUT_SECONDS,
)


def get_llm():
    """
    返回一个普通 LLM 客户端（用于结构化 JSON 输出）。
    DeepSeek 强制 json_object 模式。
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("Agent 尚未配置模型 API 密钥")
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.3,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def get_text_llm():
    """
    纯文本 LLM，不强制 JSON 输出。
    用于生成叙事化概要、开场白、剧情回应。
    """
    if not DEEPSEEK_API_KEY:
        raise RuntimeError("Agent 尚未配置模型 API 密钥")
    return ChatOpenAI(
        model=DEEPSEEK_MODEL,
        api_key=DEEPSEEK_API_KEY,
        base_url=DEEPSEEK_BASE_URL,
        temperature=0.7,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )


def get_json_llm(schema_cls):
    """
    兼容 DeepSeek 的结构化输出封装。
    手动在 Prompt 里嵌入 Schema，然后解析返回的 JSON。
    """
    llm = get_llm()
    schema_json = json.dumps(
        schema_cls.model_json_schema(), ensure_ascii=False, indent=2
    )

    def invoke(messages):
        enhanced = list(messages)
        last = enhanced[-1]
        schema_instruction = (
            f"\n\n请严格按照以下 JSON Schema 输出，只输出 JSON，不要任何额外解释：\n"
            f"```json\n{schema_json}\n```"
        )
        if isinstance(last, HumanMessage):
            enhanced[-1] = HumanMessage(content=last.content + schema_instruction)
        else:
            enhanced.append(HumanMessage(content=schema_instruction))

        response = llm.invoke(enhanced)
        content = response.content
        if not isinstance(content, str):
            raise ValueError("模型返回了非文本内容")
        text = content.strip()

        # 去掉可能的 markdown 代码块包裹
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text
            text = text.rsplit("```", 1)[0]
        text = text.strip()

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            start = text.find("{")
            end = text.rfind("}")
            if start != -1 and end != -1:
                data = json.loads(text[start:end + 1])
            else:
                raise ValueError(f"无法从返回中解析 JSON：\n{text}")

        return schema_cls(**data)

    return invoke
