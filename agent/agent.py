"""
Main Agent：自主规划 + 确认修改 + 对话式游玩。
用户只提供景区，Agent 自主完成完整剧本游策划。
"""
import os
import random
import re
from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel
from langgraph.graph import StateGraph, END
from langchain_core.messages import HumanMessage, SystemMessage

from schema import Script, Review
from prompts import (
    PLAY_OPENING_PROMPT,
    PLAY_JUDGE_PROMPT,
    CONFIRM_SUMMARY_PROMPT,
)
from llm import get_llm, get_json_llm, get_text_llm
from rag import list_available_spots
from skills import (
    Skill01_CultureAnalysis,
    Skill02_IPPlanning,
    Skill03_ScriptDesign,
    Skill04_Audit,
    Skill05_ModifyAnalysis,
)


SESSIONS: dict[str, dict] = {}


class AgentState(TypedDict):
    session_id: str
    user_input: str
    script: Script
    stage: str
    reply: str
    current_node_id: str
    node_history: list


class PlayJudge(BaseModel):
    completed: bool = False
    reply: str = ""


def make_greeting() -> tuple[str, list[str]]:
    spots = list_available_spots()
    if not spots:
        return "知识库里暂时没有景区资料，请先补充 data/nanxijiang/01_古村落空间 下的 .md 文件。", []
    sample_size = min(4, len(spots))
    options = random.sample(spots, sample_size)
    lines = ["欢迎！请选择一个你想体验的剧本景区：", ""]
    for i, opt in enumerate(options, 1):
        lines.append(f"{i}. {opt}")
    lines.append("")
    lines.append("回复序号或直接输入景区名都可以。")
    return "\n".join(lines), options


def save_script_to_file(session_id: str, script: Script, suffix: str = ""):
    """把完整剧本保存到本地 outputs 目录。"""
    os.makedirs("outputs", exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if suffix:
        safe_session_id = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)[:80] or "session"
        name = f"outputs/{safe_session_id}_{suffix}_{timestamp}.json"
    else:
        safe_session_id = re.sub(r"[^a-zA-Z0-9_-]", "_", session_id)[:80] or "session"
        name = f"outputs/{safe_session_id}_{timestamp}.json"

    try:
        with open(name, "w", encoding="utf-8") as f:
            f.write(script.model_dump_json(indent=2))
        print(f"✅ 剧本已保存到 {name}")
    except Exception as e:
        print(f"⚠️ 保存剧本失败：{e}")


def plan_and_generate_node(state: AgentState) -> dict:
    script: Script = state["script"]
    location = script.project.location

    script.project.name = f"{location}·沉浸式剧本游"
    script.project.type = "沉浸式剧本游"
    script.project.players = "2-4人"
    script.project.summary = f"以{location}为舞台的沉浸式剧本游"

    skill01 = Skill01_CultureAnalysis()
    script.culture_resources = skill01.run(location, script.project.type)

    skill02 = Skill02_IPPlanning()
    ip_bundle = skill02.run(script)
    script.ip = ip_bundle.ip
    script.world = ip_bundle.world
    script.characters = ip_bundle.characters
    script.story = ip_bundle.story

    skill03 = Skill03_ScriptDesign()
    script.spaces = skill03.run_spaces(script)
    script.plot_nodes = skill03.run_nodes(script)
    script.npcs = skill03.run_npcs(script)

    skill04 = Skill04_Audit()
    review_result = skill04.run(script)
    script.review = Review(
        issues=review_result.issues,
        passed=review_result.passed,
        fix_rounds=0,
    )

    return {"script": script, "stage": "audit_done"}


def build_summary_fallback(script: Script) -> str:
    """不依赖 LLM 的概要拼接。"""
    lines = []
    name = script.project.name or "沉浸式剧本游"
    lines.append(f"《{name}》")

    if script.ip.concept:
        lines.append(f"\n{script.ip.concept}")

    if script.world.player_identity:
        lines.append(f"\n你将以「{script.world.player_identity}」的身份进入故事。")

    if script.world.core_conflict:
        lines.append(f"核心冲突：{script.world.core_conflict}")

    if script.characters:
        names = "、".join([c.name for c in script.characters[:4] if c.name])
        if names:
            lines.append(f"\n主要角色：{names}")

    if script.plot_nodes:
        lines.append(f"\n游线共 {len(script.plot_nodes)} 个节点。")

    if script.culture_resources:
        cultures = "、".join([c.name for c in script.culture_resources[:4] if c.name])
        if cultures:
            lines.append(f"文化植入：{cultures}")

    return "\n".join(lines)


def make_confirm_summary(script: Script) -> str:
    # 先尝试 LLM 生成叙事化概要
    try:
        llm = get_text_llm()
        prompt = CONFIRM_SUMMARY_PROMPT.format(
            script_json=script.model_dump_json(indent=2)
        )
        resp = llm.invoke(
            [SystemMessage(content="你是剧本游项目汇报人。"),
             HumanMessage(content=prompt)]
        )
        text = (resp.content or "").strip()
        if text and len(text) > 20:
            return text
        print("⚠️ LLM 概要为空，使用 fallback")
    except Exception as e:
        print(f"⚠️ LLM 生成概要失败：{e}")

    return build_summary_fallback(script)


def confirm_node(state: AgentState) -> dict:
    """生成完成，进入确认环节。审查结果只保存，不展示。"""
    script: Script = state["script"]
    summary = make_confirm_summary(script)

    # 保存完整剧本到本地
    save_script_to_file(state["session_id"], script, suffix="initial")

    # 硬拼确认提示，不依赖 LLM
    hint = (
        "\n\n---\n"
        "回复「确认」开始游玩，"
        "或告诉我你想修改什么（例如：换成悬疑风格、把某个谜题改简单点、增加一个 NPC）。"
    )
    if "回复「确认」" not in summary:
        summary += hint

    return {
        "script": script,
        "stage": "confirming",
        "reply": summary,
    }


def modify_node(state: AgentState) -> dict:
    script: Script = state["script"]
    user_request = state["user_input"]

    skill05 = Skill05_ModifyAnalysis()
    plan = skill05.analyze(script, user_request)

    affected = plan.affected_modules

    if any(m in affected for m in ["ip", "world", "characters", "story"]):
        skill02 = Skill02_IPPlanning()
        ip_bundle = skill02.run(script, user_preference=user_request)
        if "ip" in affected:
            script.ip = ip_bundle.ip
        if "world" in affected:
            script.world = ip_bundle.world
        if "characters" in affected:
            script.characters = ip_bundle.characters
        if "story" in affected:
            script.story = ip_bundle.story

    if "plot_nodes" in affected:
        skill03 = Skill03_ScriptDesign()
        script.plot_nodes = skill03.run_nodes(script)
        script.npcs = skill03.run_npcs(script)

    if "npcs" in affected and "plot_nodes" not in affected:
        skill03 = Skill03_ScriptDesign()
        script.npcs = skill03.run_npcs(script)

    skill04 = Skill04_Audit()
    review_result = skill04.run(script)
    script.review = Review(
        issues=review_result.issues,
        passed=review_result.passed,
        fix_rounds=script.review.fix_rounds,
    )

    summary = make_confirm_summary(script)
    summary = f"【已根据你的要求修改】\n\n{summary}"

    # 保存修改后的完整剧本到本地
    save_script_to_file(state["session_id"], script, suffix="modified")

    # 末尾同样拼确认提示
    hint = (
        "\n\n---\n"
        "回复「确认」开始游玩，或继续告诉我你想调整什么。"
    )
    if "回复「确认」" not in summary:
        summary += hint

    return {
        "script": script,
        "stage": "confirming",
        "reply": summary,
    }


def start_play_node(state: AgentState) -> dict:
    script: Script = state["script"]
    if not script.plot_nodes:
        return {"reply": "剧本生成失败，没有剧情节点。", "stage": "done"}

    first_node = script.plot_nodes[0]
    llm = get_text_llm()
    prompt = PLAY_OPENING_PROMPT.format(
        node_json=first_node.model_dump_json(indent=2)
    )
    response = llm.invoke(
        [SystemMessage(content="你是沉浸式剧本主持人。"), HumanMessage(content=prompt)]
    )
    opening = (response.content or "").strip()

    return {
        "reply": opening,
        "stage": "playing",
        "current_node_id": first_node.node_id,
        "node_history": [first_node.node_id],
    }


_GRAPH = None


def build_graph():
    global _GRAPH
    if _GRAPH is not None:
        return _GRAPH

    graph = StateGraph(AgentState)
    graph.add_node("plan_and_generate", plan_and_generate_node)
    graph.add_node("confirm", confirm_node)
    graph.add_node("start_play", start_play_node)

    graph.set_entry_point("plan_and_generate")
    graph.add_edge("plan_and_generate", "confirm")
    graph.add_edge("confirm", END)
    graph.add_edge("start_play", END)

    _GRAPH = graph.compile()
    return _GRAPH


def find_node(script: Script, node_id: str):
    for n in script.plot_nodes:
        if n.node_id == node_id:
            return n
    return None


def play_chat(session_id: str, user_message: str) -> dict:
    state = SESSIONS[session_id]
    script: Script = state["script"]
    current_id = state.get("current_node_id", "")
    current_node = find_node(script, current_id)

    if current_node is None:
        return {"reply": "剧本已结束。", "stage": "finished", "script": {}}

    history = "\n".join(
        f"{m['role']}: {m['content']}" for m in state["messages"][-6:]
    )
    prompt = PLAY_JUDGE_PROMPT.format(
        node_json=current_node.model_dump_json(indent=2),
        user_input=user_message,
        history=history,
    )
    invoke = get_json_llm(PlayJudge)
    result: PlayJudge = invoke(
        [SystemMessage(content="你是沉浸式剧本主持人。"), HumanMessage(content=prompt)]
    )

    reply = result.reply

    if result.completed:
        if current_node.rewards:
            reward_lines = ["【获得】"]
            for r in current_node.rewards:
                reward_lines.append(f"· {r.name}：{r.description}")
            reply += "\n\n" + "\n".join(reward_lines)

        if current_node.closing_narration:
            reply += "\n\n" + current_node.closing_narration

        next_id = current_node.next_node_id
        if next_id:
            next_node = find_node(script, next_id)
            if next_node:
                state["current_node_id"] = next_id
                state["node_history"].append(next_id)
                llm = get_text_llm()
                open_prompt = PLAY_OPENING_PROMPT.format(
                    node_json=next_node.model_dump_json(indent=2)
                )
                resp = llm.invoke(
                    [SystemMessage(content="你是沉浸式剧本主持人。"),
                     HumanMessage(content=open_prompt)]
                )
                reply += "\n\n" + (resp.content or "").strip()
        else:
            reply += "\n\n【剧本结束】感谢你的体验！"
            state["stage"] = "finished"

    state["messages"].append({"role": "user", "content": user_message})
    state["messages"].append({"role": "assistant", "content": reply})
    SESSIONS[session_id] = state

    return {"reply": reply, "stage": state["stage"], "script": {}}


CONFIRM_KEYWORDS = {"确认", "开始", "没问题", "开玩", "ok", "好了", "可以了", "确认开始"}


def is_confirm(user_input: str) -> bool:
    normalized = re.sub(r"[\s，。！？,.!?]", "", user_input).lower()
    return normalized in CONFIRM_KEYWORDS


def chat(session_id: str, user_message: str) -> dict:
    if session_id not in SESSIONS:
        greeting, spot_options = make_greeting()
        SESSIONS[session_id] = {
            "session_id": session_id,
            "messages": [{"role": "assistant", "content": greeting}],
            "user_input": "",
            "script": Script(),
            "stage": "ask_user",
            "reply": greeting,
            "current_node_id": "",
            "node_history": [],
            "spot_options": spot_options,
        }
        return {"reply": greeting, "script": {}, "stage": "ask_user"}

    state = SESSIONS[session_id]
    stage = state.get("stage", "")

    if stage == "finished":
        return {"reply": "剧本已结束，感谢你的体验！", "stage": "finished", "script": {}}

    if stage == "playing":
        return play_chat(session_id, user_message)

    if stage == "confirming":
        state["messages"].append({"role": "user", "content": user_message})
        if is_confirm(user_message):
            state["user_input"] = user_message
            result = start_play_node(state)
            state.update(result)
            state["messages"].append(
                {"role": "assistant", "content": result.get("reply", "")}
            )
            SESSIONS[session_id] = state
            return {
                "reply": result.get("reply", ""),
                "script": state["script"].model_dump(mode="json"),
                "stage": result.get("stage", ""),
            }
        else:
            state["user_input"] = user_message
            result = modify_node(state)
            state.update(result)
            state["messages"].append(
                {"role": "assistant", "content": result.get("reply", "")}
            )
            SESSIONS[session_id] = state
            return {
                "reply": result.get("reply", ""),
                "script": {},
                "stage": result.get("stage", ""),
            }

    if stage == "ask_user":
        spots = list_available_spots()
        shown_spots = state.get("spot_options") or spots
        chosen = None
        try:
            idx = int(user_message.strip()) - 1
            if 0 <= idx < len(shown_spots):
                chosen = shown_spots[idx]
        except ValueError:
            pass
        if not chosen:
            for s in spots:
                if s in user_message:
                    chosen = s
                    break
        if not chosen:
            return {
                "reply": "我没识别出景区名，请回复序号或输入完整景区名。",
                "script": {},
                "stage": "ask_user",
            }

        state["script"].project.location = chosen
        state["messages"].append({"role": "user", "content": user_message})

        state["stage"] = "generating"
        graph = build_graph()
        try:
            result = graph.invoke(state)
        except Exception:
            state["stage"] = "ask_user"
            SESSIONS[session_id] = state
            return {
                "reply": "本次生成没有完成，请稍后重试或重新选择景区。",
                "script": {},
                "stage": "ask_user",
            }

        # 把 result 合并回 state，保留 messages
        state.update(result)
        state["messages"].append(
            {"role": "assistant", "content": state.get("reply", "")}
        )
        SESSIONS[session_id] = state

        return {
            "reply": state.get("reply", ""),
            "script": state["script"].model_dump(mode="json"),
            "stage": state.get("stage", ""),
        }

    return {"reply": "状态异常。", "script": {}, "stage": "error"}
