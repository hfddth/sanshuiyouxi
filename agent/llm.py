"""
LLM 客户端工厂。支持 DeepSeek / Claude / Ollama 三种，通过 config.LLM_PROVIDER 切换。
提供 get_llm()、get_structured_llm(schema)、get_json_llm(schema_cls)、get_text_llm() 四个入口。
"""
import json
from langchain_core.messages import HumanMessage, SystemMessage

from config import (
    LLM_PROVIDER,
    DEEPSEEK_API_KEY, DEEPSEEK_BASE_URL, DEEPSEEK_MODEL,
    ANTHROPIC_API_KEY, ANTHROPIC_MODEL,
    OLLAMA_BASE_URL, OLLAMA_MODEL,
)


def get_llm():
    """
    返回一个普通 LLM 客户端（用于结构化 JSON 输出）。
    DeepSeek 强制 json_object 模式。
    """
    if LLM_PROVIDER == "deepseek":
        from langchain_openai import ChatOpenAI
        if not DEEPSEEK_API_KEY:
            raise ValueError("缺少 DEEPSEEK_API_KEY，请在 .env 中配置")
        return ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.3,
            model_kwargs={"response_format": {"type": "json_object"}},
        )

    elif LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.3,
            format="json",
        )

    elif LLM_PROVIDER == "claude":
        from langchain_anthropic import ChatAnthropic
        if not ANTHROPIC_API_KEY:
            raise ValueError("缺少 ANTHROPIC_API_KEY，请在 .env 中配置")
        return ChatAnthropic(
            model=ANTHROPIC_MODEL,
            api_key=ANTHROPIC_API_KEY,
            temperature=0.3,
        )

    else:
        raise ValueError(f"未知 LLM_PROVIDER: {LLM_PROVIDER}")


def get_text_llm():
    """
    纯文本 LLM，不强制 JSON 输出。
    用于生成叙事化概要、开场白、剧情回应。
    """
    if LLM_PROVIDER == "deepseek":
        from langchain_openai import ChatOpenAI
        if not DEEPSEEK_API_KEY:
            raise ValueError("缺少 DEEPSEEK_API_KEY，请在 .env 中配置")
        return ChatOpenAI(
            model=DEEPSEEK_MODEL,
            api_key=DEEPSEEK_API_KEY,
            base_url=DEEPSEEK_BASE_URL,
            temperature=0.7,
        )

    elif LLM_PROVIDER == "ollama":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=OLLAMA_MODEL,
            base_url=OLLAMA_BASE_URL,
            temperature=0.7,
        )

    elif LLM_PROVIDER == "claude":
        from langchain_anthropic import ChatAnthropic
        if not ANTHROPIC_API_KEY:
            raise ValueError("缺少 ANTHROPIC_API_KEY，请在 .env 中配置")
        return ChatAnthropic(
            model=ANTHROPIC_MODEL,
            api_key=ANTHROPIC_API_KEY,
            temperature=0.7,
        )

    else:
        raise ValueError(f"未知 LLM_PROVIDER: {LLM_PROVIDER}")


def get_structured_llm(schema):
    """
    返回一个带结构化输出约束的 LLM，输出必须符合 schema（Pydantic 模型）。
    注意：DeepSeek 当前不支持 json_schema，此函数仅适用于支持该能力的模型。
    """
    llm = get_llm()
    return llm.with_structured_output(schema)


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
        text = response.content.strip()

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