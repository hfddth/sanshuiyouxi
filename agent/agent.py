"""
文旅剧本游策划 Agent

为景区提供沉浸式剧本游策划服务。
用户（景区运营方）选择景区后，Agent 分阶段生成完整的剧本游策划案。

流程：
① IP方向与世界观 → 确认
② 人物与故事梗概 → 确认
③ 用户输入景点 → 剧情结构与景点绑定 → 确认
④ 剧情节点逐个生成 → 每个节点确认
   - 用户可修改当前节点
   - 用户可提出修改上游内容，需确认后重新生成下游
⑤ 输出格式化完整策划案 → 确认/修改

支持的景区：
- 本地知识库已收录的景区（优先使用本地资料）
- 本地未收录的景区（先联网验证真实性，通过后联网补充资料）

保存：
- outputs(标准)/xxx.json：4 个核心对象，符合前端可视化规范
- outputs(完整)/xxx.json：完整策划案，含 7 个扩展字段，供存档与评审
"""
import os
import uuid
import random
from datetime import datetime
from typing import TypedDict

from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage

from schema import (
    Script, Review, Space, PlotNode,
    WorldInfo, StoryInfo, PlotStructure,
)
from prompts import SYSTEM_PROMPT
from llm import get_text_llm, get_json_llm
from rag import list_available_spots, retrieve_multi_dimension, deepseek_web_search
from skills import (
    Skill01_CultureAnalysis,
    Skill02a_IPAndWorld,
    Skill02b_CharactersAndStory,
    Skill03b_PlotStructure,
    Skill03c_SingleNode,
    Skill03d_NPCs,
    Skill04_Audit,
    Skill05_ModifyAnalysis,
)


SESSIONS: dict[str, dict] = {}

_SPOT_VERIFY_CACHE: dict[str, tuple] = {}


NANXIJIANG_INTRO = (
    "楠溪江不只是一个景点，它是国家级风景名胜区、国家 4A 级旅游区，"
    "目前正在全力创建国家 5A 级旅游景区。"
    "它包含多个古村落和自然景区，每个都可以单独做剧本游策划。"
)

MIN_SPACES = 3
MAX_SPACES = 6


CONFIRM_KEYWORDS = [
    "确认", "继续", "没问题", "可以", "ok", "OK", "好", "下一", "下一步",
    "够了", "就这些", "没有了", "开始", "嗯", "行", "是的", "对",
    "go", "yes", "好嘞", "中", "成", "妥",
]

MODIFY_KEYWORDS = ["换", "改", "调整", "重新", "不要", "删除", "去掉", "再加", "再加一个", "增加"]


def is_confirm(message: str) -> bool:
    """Return whether a reply is an explicit confirmation."""
    normalized = message.strip().lower().rstrip("!！。.")
    return normalized in {"确认", "确定", "可以", "同意", "通过", "ok", "okay", "yes", "好"}


UPSTREAM_MODULE_NAMES = {
    "upstream_ip": "IP 定位",
    "upstream_world": "世界观",
    "upstream_characters": "角色",
    "upstream_story": "故事主线",
    "upstream_structure": "剧情结构",
}


STAGE_PROGRESS = {
    "ask_user":                     {"step": 0, "total": 5, "name": "选择景区", "status": "confirming"},
    "stage1_confirm":               {"step": 1, "total": 5, "name": "IP 与世界观", "status": "confirming"},
    "stage2_confirm":               {"step": 2, "total": 5, "name": "人物与故事梗概", "status": "confirming"},
    "stage3_input_spaces":          {"step": 3, "total": 5, "name": "选择景点", "status": "confirming"},
    "stage3_confirm":               {"step": 3, "total": 5, "name": "剧情结构与景点绑定", "status": "confirming"},
    "stage4_confirm":               {"step": 4, "total": 5, "name": "剧情节点", "status": "confirming"},
    "stage4_confirm_upstream":      {"step": 4, "total": 5, "name": "确认修改上游", "status": "confirming"},
    "stage5_confirm":               {"step": 5, "total": 5, "name": "整体审查与最终输出", "status": "confirming"},
    "finished":                     {"step": 5, "total": 5, "name": "策划案已完成", "status": "finished"},
}


def get_progress(stage: str) -> dict:
    return STAGE_PROGRESS.get(stage, {"step": 0, "total": 5, "name": "", "status": "confirming"})


def get_next_hint(stage: str) -> str:
    hints = {
        "ask_user": "AI 思考中 · 正在识别景区名称，必要时联网核查...",
        "stage1_confirm": "AI 思考中 · 正在调用剧本写作 Skill，构建 IP 与世界观框架...",
        "stage2_confirm": "AI 思考中 · 正在调用角色设计 Skill，生成人物与故事主线...",
        "stage3_input_spaces": "AI 思考中 · 正在解析景点语义，必要时联网核查景点归属...",
        "stage3_confirm": "AI 思考中 · 正在规划剧情结构，匹配真实空间与剧情节点...",
        "stage4_confirm": "AI 思考中 · 正在生成剧情节点，校验线索合理性与空间可行性...",
        "stage4_confirm_upstream": "正在等待您确认是否修改上游内容...",
        "stage5_confirm": "AI 思考中 · 正在生成 NPC，执行六维审查协议（世界观 / 剧情 / 可玩性 / 空间 / 文化真实性 / 实施可行性）...",
        "finished": "策划案已完成。",
    }
    return hints.get(stage, "AI 思考中 · 正在处理...")


class AgentState(TypedDict):
    session_id: str
    user_input: str
    script: Script
    stage: str
    reply: str


class SpaceListLocal(BaseModel):
    spaces: list[Space] = []


class NewSpaceCheck(BaseModel):
    is_valid: bool = False
    name: str = ""
    type: str = ""
    description: str = ""


class IntentResult(BaseModel):
    intent: str = "unknown"
    reason: str = ""


class SpotResolveResult(BaseModel):
    is_spot: bool = False
    spot_name: str = ""
    is_region: bool = False
    reason: str = ""


class SpotVerifyResult(BaseModel):
    exists: bool = False
    standard_name: str = ""
    location: str = ""
    reason: str = ""


class ModifyTargetResult(BaseModel):
    target: str = "unknown"
    reason: str = ""


def calc_total_nodes(space_count: int) -> int:
    return max(3, min(8, space_count + 2))


def to_frontend_dict(script: Script) -> dict:
    """只导出前端可视化规范要求的 4 个核心对象。"""
    return {
        "project": script.project.model_dump(),
        "spaces": [s.model_dump() for s in script.spaces],
        "plot_nodes": [n.model_dump() for n in script.plot_nodes],
        "npcs": [n.model_dump() for n in script.npcs],
    }


def make_response(reply: str, script, stage: str, loading_hint: str = "") -> dict:
    return {
        "reply": reply,
        "script": to_frontend_dict(script) if script else {},
        "stage": stage,
        "progress": get_progress(stage),
        "loading_hint": loading_hint or get_next_hint(stage),
        "next_hint": get_next_hint(stage),
    }


def get_session_state(session_id: str) -> dict:
    if session_id not in SESSIONS:
        return {"error": "会话不存在"}
    state = SESSIONS[session_id]
    stage = state.get("stage", "")
    script = state.get("script")
    return {
        "stage": stage,
        "progress": get_progress(stage),
        "loading_hint": get_next_hint(stage),
        "next_hint": get_next_hint(stage),
        "script": to_frontend_dict(script) if script else {},
    }


def judge_intent(user_message: str, stage_desc: str) -> str:
    msg = user_message.strip()

    if len(msg) <= 8:
        for kw in CONFIRM_KEYWORDS:
            if kw in msg or msg.lower() == kw.lower():
                return "confirm"
        for kw in MODIFY_KEYWORDS:
            if kw in msg:
                return "modify"

    prompt = f"""你在识别景区策划者在剧本游策划流程中的意图。

当前阶段：{stage_desc}
用户刚刚说：{user_message}

可能的意图：
- confirm：同意、确认、继续、没问题、可以、进入下一步、下一阶段、够了、就这些、没有了、开始吧、ok、好的、go、yes、嗯、行、继续吧、可以了、就这样 等肯定性回应
- modify：修改当前阶段内容
- add：想增加内容
- remove：想删除内容
- unknown：无法判断

输出 JSON：{{"intent": "confirm 或 modify 或 add 或 remove 或 unknown", "reason": "一句话理由"}}
"""
    try:
        invoke = get_json_llm(IntentResult)
        result = invoke([
            SystemMessage(content="你是意图识别助手。"),
            HumanMessage(content=prompt),
        ])
        intent = result.intent.strip().lower()
        if intent in ("confirm", "modify", "add", "remove", "unknown"):
            return intent
        return "unknown"
    except Exception as e:
        print(f"⚠️ 意图识别失败：{e}")
        return "unknown"


def judge_modify_target(user_message: str) -> tuple:
    prompt = f"""用户正在剧本游策划的节点生成阶段。当前正在逐个生成剧情节点，已经生成了部分节点。

用户刚刚说：{user_message}

请判断用户想修改的对象：
- current_node：当前这个节点的内容（场景、任务、线索、互动、奖励、旁白）
- upstream_ip：IP 名称、定位、卖点、目标游客、视觉风格
- upstream_world：世界观
- upstream_characters：角色
- upstream_story：故事主线
- upstream_structure：剧情结构
- unknown：无法判断

只输出 JSON：
{{"target": "current_node 或 upstream_ip 或 upstream_world 或 upstream_characters 或 upstream_story 或 upstream_structure 或 unknown", "reason": "一句话理由"}}
"""
    try:
        invoke = get_json_llm(ModifyTargetResult)
        result = invoke([
            SystemMessage(content="你是修改对象识别助手。"),
            HumanMessage(content=prompt),
        ])
        return result.target, result.reason
    except Exception as e:
        print(f"⚠️ 修改对象识别失败：{e}")
        return "unknown", ""


def clear_downstream(script: Script, module: str):
    if module == "upstream_ip":
        script.world = WorldInfo()
        script.characters = []
        script.story = StoryInfo()
        script.plot_structure = PlotStructure()
        script.plot_nodes = []
        script.npcs = []
    elif module == "upstream_world":
        script.characters = []
        script.story = StoryInfo()
        script.plot_structure = PlotStructure()
        script.plot_nodes = []
        script.npcs = []
    elif module == "upstream_characters":
        script.story = StoryInfo()
        script.plot_structure = PlotStructure()
        script.plot_nodes = []
        script.npcs = []
    elif module == "upstream_story":
        script.plot_structure = PlotStructure()
        script.plot_nodes = []
        script.npcs = []
    elif module == "upstream_structure":
        script.plot_nodes = []
        script.npcs = []


def make_greeting() -> tuple[str, list[str]]:
    options = list_available_spots()[:6]
    greeting = (
        "您好！我是永嘉文旅剧本游策划助手，专门为永嘉景区提供沉浸式剧本游策划服务。\n\n"
        "我们分工协作：我负责整理素材、搭建剧本框架、设计故事与玩法并迭代优化；您来把控方向、敲定方案。\n\n"
        "现在，请告诉我您想策划的景区名称，我就可以开始构思方案。\n\n"
        + "\n".join(f"{index}. {option}" for index, option in enumerate(options, 1))
    )
    return greeting, options


def make_spot_list_reply(spots: list, prefix: str = "") -> str:
    lines = []
    if prefix:
        lines.append(prefix)
        lines.append("")
    lines.append("可选景区如下：")
    lines.append("")
    for i, s in enumerate(spots, 1):
        lines.append(f"{i}. {s}")
    lines.append("")
    lines.append("回复序号或直接输入景区名。")
    return "\n".join(lines)


def save_script(session_id: str, script: Script, suffix: str = ""):
    """
    保存两份：
    - outputs(标准)/xxx.json：只含 4 个核心对象，符合前端可视化规范
    - outputs(完整)/xxx.json：完整策划案，含 7 个扩展字段，供存档与评审
    """
    import json
    os.makedirs("outputs(标准)", exist_ok=True)
    os.makedirs("outputs(完整)", exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    if suffix:
        filename = f"{session_id}_{suffix}_{ts}.json"
    else:
        filename = f"{session_id}_{ts}.json"

    frontend_path = os.path.join("outputs(标准)", filename)
    full_path = os.path.join("outputs(完整)", filename)

    try:
        with open(frontend_path, "w", encoding="utf-8") as f:
            json.dump(to_frontend_dict(script), f, ensure_ascii=False, indent=2)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(script.model_dump_json(indent=2))
        print(f"✅ 策划案已保存：")
        print(f"   标准版：{frontend_path}")
        print(f"   完整版：{full_path}")
    except Exception as e:
        print(f"⚠️ 保存失败：{e}")


# ===== 格式化输出 =====

def format_node_card(node: PlotNode, space_name: str, index: int, total: int) -> str:
    lines = []
    lines.append("━" * 30)
    lines.append(f"节点 {node.node_id}　({index}/{total})")
    lines.append("━" * 30)
    lines.append(f"标题：{node.title}")
    lines.append(f"空间：{space_name}")
    lines.append("")
    lines.append("【场景】")
    lines.append(f"  {node.scene.get('description', '')}")
    if node.scene.get("plot"):
        lines.append(f"  {node.scene.get('plot', '')}")
    lines.append("")
    lines.append("【开场旁白】")
    lines.append(f"  {node.opening_narration}")
    lines.append("")
    lines.append("【任务】")
    lines.append(f"  目标：{node.task.objective}")
    if node.task.player_actions:
        lines.append("  玩家动作：")
        for i, act in enumerate(node.task.player_actions, 1):
            lines.append(f"    {i}. {act}")
    lines.append(f"  完成条件：{node.task.completion_condition}")
    lines.append("")
    lines.append("【互动】")
    lines.append(f"  类型：{node.interaction.type}")
    lines.append(f"  说明：{node.interaction.description}")
    if node.clues:
        lines.append("")
        lines.append("【线索】")
        for c in node.clues:
            lines.append(f"  · {c.name}：{c.content}")
    if node.culture:
        lines.append("")
        lines.append("【文化依据】")
        for c in node.culture:
            lines.append(f"  · {c.name}")
            if c.integration:
                lines.append(f"    融合：{c.integration}")
    if node.rewards:
        lines.append("")
        lines.append("【奖励】")
        for r in node.rewards:
            lines.append(f"  · {r.name}：{r.description}")
    lines.append("")
    lines.append("【结语】")
    lines.append(f"  {node.closing_narration}")
    lines.append("")
    lines.append("━" * 30)
    lines.append("回复「确认」生成下一个节点，或告诉我想调整这个节点。")
    return "\n".join(lines)


def format_full_script(script: Script) -> str:
    lines = []
    lines.append("=" * 40)
    lines.append(f"  《{script.project.name}》")
    lines.append(f"  {script.project.location} · 沉浸式剧本游策划案")
    lines.append("=" * 40)

    lines.append("")
    lines.append("【一、项目信息】")
    lines.append(f"  景区：{script.project.location}")
    lines.append(f"  类型：{script.project.type}")
    lines.append(f"  时长：{script.project.duration}")
    lines.append(f"  建议人数：{script.project.players}")

    lines.append("")
    lines.append("【二、IP 定位】")
    lines.append(f"  名称：{script.ip.name}")
    lines.append(f"  概念：{script.ip.concept}")
    lines.append(f"  定位：{script.ip.positioning}")
    lines.append(f"  卖点：{script.ip.selling_point}")
    lines.append(f"  目标游客：{script.ip.target_audience}")
    lines.append(f"  视觉风格：{script.ip.visual_style}")

    lines.append("")
    lines.append("【三、世界观】")
    lines.append(f"  时间背景：{script.world.time_setting}")
    lines.append(f"  世界规则：{script.world.world_rules}")
    lines.append(f"  核心冲突：{script.world.core_conflict}")
    lines.append(f"  玩家身份：{script.world.player_identity}")
    lines.append(f"  玩家目标：{script.world.player_goal}")

    lines.append("")
    lines.append("【四、角色】")
    for c in script.characters:
        lines.append(f"  · {c.name}（{c.role}）")
        if c.personality:
            lines.append(f"    性格：{c.personality}")
        if c.function:
            lines.append(f"    功能：{c.function}")

    lines.append("")
    lines.append("【五、故事主线】")
    lines.append(f"  梗概：{script.story.synopsis}")
    if script.story.background:
        lines.append(f"  背景：{script.story.background}")
    if script.story.event:
        lines.append(f"  事件：{script.story.event}")
    if script.story.conflict_escalation:
        lines.append(f"  冲突升级：{script.story.conflict_escalation}")
    if script.story.climax:
        lines.append(f"  高潮：{script.story.climax}")
    if script.story.ending:
        lines.append(f"  结局：{script.story.ending}")

    lines.append("")
    lines.append("【六、剧情结构】")
    for act in script.plot_structure.acts:
        act_name = act.get("act", "")
        goal = act.get("goal", "")
        lines.append(f"  {act_name}：{goal}")
        for title in act.get("node_titles", []):
            lines.append(f"    · {title}")

    lines.append("")
    lines.append("=" * 40)
    lines.append("  七、剧情节点")
    lines.append("=" * 40)
    for i, node in enumerate(script.plot_nodes, 1):
        space_name = ""
        for s in script.spaces:
            if s.space_id == node.space_id:
                space_name = s.name
                break
        lines.append("")
        lines.append(f"  ── {node.node_id}　{node.title} ──")
        lines.append(f"  空间：{space_name}")
        lines.append(f"  开场：{node.opening_narration}")
        lines.append(f"  任务目标：{node.task.objective}")
        if node.task.player_actions:
            lines.append(f"  玩家动作：{'；'.join(node.task.player_actions)}")
        if node.interaction.type:
            lines.append(f"  互动类型：{node.interaction.type}")
        if node.clues:
            lines.append(f"  线索：{'；'.join(c.name for c in node.clues)}")
        if node.culture:
            lines.append(f"  文化依据：{'；'.join(c.name for c in node.culture)}")
        if node.rewards:
            lines.append(f"  奖励：{'；'.join(r.name for r in node.rewards)}")
        lines.append(f"  结语：{node.closing_narration}")

    lines.append("")
    lines.append("=" * 40)
    lines.append("  八、NPC")
    lines.append("=" * 40)
    for n in script.npcs:
        lines.append(f"  · {n.name}（{n.role}）")
        if n.personality:
            lines.append(f"    性格：{n.personality}")
        if n.background:
            lines.append(f"    背景：{n.background}")

    lines.append("")
    lines.append("=" * 40)
    lines.append("  九、文化资源")
    lines.append("=" * 40)
    for c in script.culture_resources:
        lines.append(f"  · {c.name}（{c.authenticity}）")
        if c.description:
            lines.append(f"    {c.description}")

    lines.append("")
    lines.append("=" * 40)
    lines.append("  策划案已完成")
    lines.append("=" * 40)
    return "\n".join(lines)


# ===== 阶段 1：IP 与世界观 =====
def run_stage1(state: AgentState, user_preference: str = "") -> str:
    script: Script = state["script"]
    skill = Skill02a_IPAndWorld()
    bundle = skill.run(script, user_preference=user_preference)
    script.ip = bundle.ip
    script.world = bundle.world

    if not script.project.summary:
        concept = script.ip.concept or f"以{script.project.location}为舞台的沉浸式剧本游"
        script.project.summary = concept[:60]

    text = f"""【第一阶段：IP 方向与世界观】

IP 名称：{script.ip.name}
概念：{script.ip.concept}
定位：{script.ip.positioning}
卖点：{script.ip.selling_point}
目标游客：{script.ip.target_audience}
视觉风格：{script.ip.visual_style}

世界观：
· 时间背景：{script.world.time_setting}
· 世界规则：{script.world.world_rules}
· 事件起因：{script.world.event_cause}
· 核心冲突：{script.world.core_conflict}
· 玩家身份：{script.world.player_identity}
· 玩家目标：{script.world.player_goal}
· 真实文化与虚构的关系：{script.world.culture_relation}

---
回复「确认」进入下一步（人物与故事梗概），或告诉我想调整什么。"""
    state["stage"] = "stage1_confirm"
    return text


# ===== 阶段 2：人物与故事梗概 =====
def run_stage2(state: AgentState, user_preference: str = "") -> str:
    script: Script = state["script"]
    skill = Skill02b_CharactersAndStory()
    bundle = skill.run(script, user_preference=user_preference)
    script.characters = bundle.characters
    script.story = bundle.story

    chars = "\n".join(
        f"· {c.name}（{c.role}）：{c.function}"
        for c in script.characters
    )
    text = f"""【第二阶段：人物与故事梗概】

主要角色：
{chars}

故事梗概：
{script.story.synopsis}

· 背景：{script.story.background}
· 事件：{script.story.event}
· 玩家介入：{script.story.player_intervention}
· 冲突升级：{script.story.conflict_escalation}
· 高潮：{script.story.climax}
· 结局：{script.story.ending}

---
回复「确认」进入下一步（选择景点），或告诉我想调整什么。"""
    state["stage"] = "stage2_confirm"
    return text


# ===== 阶段 3：选择景点 =====
def run_stage3_prompt(state: AgentState) -> str:
    script: Script = state["script"]

    if not script.spaces:
        context = retrieve_multi_dimension(script.project.location, "空间")
        prompt = f"""为剧本「{script.project.name}」提取候选景点。

知识库资料：
{context}

要求：
1. 提取 5-8 个真实存在于该景区的景点
2. 每个 space 有 space_id（S01 起）、name、type、description
3. map_position 不知道就填 {{"x": 0, "y": 0}}
4. 输出 JSON
"""
        invoke = get_json_llm(SpaceListLocal)
        result = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        script.spaces = result.spaces

    state["selected_space_names"] = []
    state["stage"] = "stage3_input_spaces"
    state["force_confirm"] = False
    return _format_stage3_reply(state, "【第三阶段：选择景点】")


def _parse_space_picks(user_message: str, candidates: list) -> list:
    picked = []
    for token in user_message.replace("，", ",").replace("、", ",").split(","):
        token = token.strip()
        try:
            idx = int(token) - 1
            if 0 <= idx < len(candidates):
                if candidates[idx].name not in picked:
                    picked.append(candidates[idx].name)
        except ValueError:
            pass
    for s in candidates:
        if s.name in user_message and s.name not in picked:
            picked.append(s.name)
    return picked


def _try_add_new_space(state: AgentState, user_message: str) -> str:
    script: Script = state["script"]
    location = script.project.location

    try:
        web_info = deepseek_web_search(f"永嘉县 {location} {user_message} 景点")
    except Exception as e:
        print(f"⚠️ 联网搜索失败：{e}")
        web_info = ""

    prompt = f"""用户想在剧本游「{location}」中使用一个景点：「{user_message}」

请判断：
1. 这个景点是否真实存在于「{location}」景区范围内？
2. 如果存在，给出标准名称、类型、简短描述
3. 如果不存在或无法确认，is_valid 设为 false

联网搜索参考：
{web_info}

只输出 JSON：
{{"is_valid": true/false, "name": "标准名称", "type": "类型", "description": "简短描述"}}
"""
    try:
        invoke = get_json_llm(NewSpaceCheck)
        result = invoke([
            SystemMessage(content="你是景点核查助手。"),
            HumanMessage(content=prompt),
        ])
        if result.is_valid and result.name:
            new_space = Space(
                space_id=f"S{len(script.spaces) + 1:02d}",
                name=result.name,
                type=result.type,
                description=result.description,
            )
            script.spaces.append(new_space)
            return result.name
        return "rejected"
    except Exception as e:
        print(f"⚠️ 联网查证失败：{e}")
        return "unknown"


def _format_stage3_reply(state: AgentState, prefix: str = "") -> str:
    selected = state.get("selected_space_names", [])
    script: Script = state["script"]

    lines = []
    if prefix:
        lines.append(prefix)
        lines.append("")

    if selected:
        lines.append(f"当前已选 {len(selected)} 个景点：")
        for i, name in enumerate(selected, 1):
            lines.append(f"  {i}. {name}")
    else:
        lines.append("当前还没有选择景点。")

    lines.append("")
    lines.append("候选景点：")
    for i, s in enumerate(script.spaces, 1):
        lines.append(f"  {i}. {s.name}")

    lines.append("")
    lines.append("您可以：")
    lines.append(f"· 继续输入景点名或序号，追加更多（建议至少 {MIN_SPACES} 个，最多 {MAX_SPACES} 个）")
    lines.append("· 说“你帮我选”自动挑 3-5 个")
    lines.append("· 说“够了”“就这些”“确认”开始生成剧情结构")
    lines.append("· 候选里没有的景点也可以直接说，我会联网查证")
    return "\n".join(lines)


def run_stage3_handle_input(state: AgentState, user_message: str) -> str:
    script: Script = state["script"]
    selected = state.get("selected_space_names", [])
    candidates = script.spaces

    if any(k in user_message for k in ["你帮我选", "帮我选", "自动选", "随便选"]):
        selected = [s.name for s in candidates[:5]]
        state["selected_space_names"] = selected
        return _format_stage3_reply(state, f"已自动为您选择 {len(selected)} 个景点。")

    picked = _parse_space_picks(user_message, candidates)

    if not picked:
        new_name = _try_add_new_space(state, user_message)
        if new_name == "rejected":
            return _format_stage3_reply(
                state,
                f"「{user_message}」不属于「{script.project.location}」，暂不加入。",
            )
        elif new_name == "unknown":
            return _format_stage3_reply(
                state,
                f"无法确认「{user_message}」是否属于该景区，请换个说法或从候选里选。",
            )
        else:
            picked = [new_name]

    added = 0
    for name in picked:
        if name not in selected:
            selected.append(name)
            added += 1
    state["selected_space_names"] = selected

    msg = f"已加入 {added} 个景点。" if added else "这些景点已在列表中。"
    return _format_stage3_reply(state, msg)


def run_stage3_generate(state: AgentState, selected_names: list) -> str:
    script: Script = state["script"]
    selected = [s for s in script.spaces if s.name in selected_names]
    if not selected:
        selected = script.spaces[:5]
    script.spaces = selected

    total_nodes = calc_total_nodes(len(selected))
    state["total_nodes"] = total_nodes

    skill = Skill03b_PlotStructure()
    plot_structure = skill.run(script, selected, total_nodes)
    script.plot_structure = plot_structure

    acts_text = ""
    for act in plot_structure.acts:
        act_name = act.get("act", "")
        goal = act.get("goal", "")
        titles = "、".join(act.get("node_titles", []))
        acts_text += f"\n{act_name}：{goal}\n  包含节点：{titles}"

    bindings_text = "\n".join(
        f"· {b.get('node_title', '')} → {b.get('space_name', '')}（{b.get('reason', '')}）"
        for b in plot_structure.space_bindings
    )

    text = f"""【第三阶段：剧情结构与景点绑定】

已选景点（{len(selected)} 个）：
{chr(10).join(f'· {s.name}' for s in script.spaces)}

剧情分幕：
{acts_text}

景点绑定：
{bindings_text}

预计生成 {total_nodes} 个剧情节点（根据景点数动态计算）。

---
回复「确认」开始逐个生成剧情节点，或告诉我想调整什么。"""
    state["stage"] = "stage3_confirm"
    state["planned_node_titles"] = [
        t for a in plot_structure.acts for t in a.get("node_titles", [])
    ]
    state["current_node_index"] = 0
    return text


# ===== 阶段 4：逐个生成节点 =====
def run_stage4_next_node(state: AgentState) -> str:
    script: Script = state["script"]
    idx = state.get("current_node_index", 0)
    planned = state.get("planned_node_titles", [])

    if idx >= len(planned):
        return run_stage5_final(state)

    node_title = planned[idx]

    skill = Skill03c_SingleNode()
    node = skill.run(
        script,
        node_index=idx + 1,
        total_nodes=len(planned),
        node_title=node_title,
        previous_nodes=script.plot_nodes,
    )

    if script.plot_nodes:
        script.plot_nodes[-1].next_node_id = node.node_id
        node.prerequisites = [script.plot_nodes[-1].node_id]

    script.plot_nodes.append(node)
    state["stage"] = "stage4_confirm"

    space_name = ""
    for s in script.spaces:
        if s.space_id == node.space_id:
            space_name = s.name
            break

    return format_node_card(node, space_name, idx + 1, len(planned))


# ===== 阶段 5：NPC + 审查 + 格式化完整策划案 =====
def run_stage5_final(state: AgentState) -> str:
    script: Script = state["script"]

    audit_intro = """【第五阶段：整体审查与最终输出】

正在执行六维审查协议，请您稍候：

① 正在审查剧情整体逻辑性——检查节点之间的因果关系是否连贯，前后情节能否顺畅衔接；
② 正在审查线索的连贯性——检查每一条线索的发现、推理、指向是否前后勾连，玩家能否通过线索自然推导出下一步；
③ 正在审查任务的可执行性——检查每个任务的目标是否明确、玩家动作是否可操作、完成条件是否可判定；
④ 正在审查空间与剧情的匹配度——检查剧情节点是否真实落在所选景点上，同一空间的多个节点是否有区域或时段区分；
⑤ 正在审查文化元素的融合度——检查永嘉本地文化（谢灵运诗、永昆、道情、耕读文化等）是否真正进入玩法，而非简单堆砌；
⑥ 正在审查整体实施可行性——检查互动类型是否合理、技术手段是否必要、NPC 与道具是否具备落地条件。

审查完成，正在生成最终策划案...

"""

    skill_npc = Skill03d_NPCs()
    script.npcs = skill_npc.run(script)

    skill_audit = Skill04_Audit()
    result = skill_audit.run(script)
    script.review = Review(
        issues=result.issues, passed=result.passed, fix_rounds=0
    )

    save_script(state["session_id"], script, suffix="final")

    state["stage"] = "stage5_confirm"
    return audit_intro + format_full_script(script)


# ===== 景区识别 =====
def resolve_spot(user_message: str, spots: list):
    msg = user_message.strip()

    try:
        idx = int(msg) - 1
        if 0 <= idx < len(spots):
            return spots[idx], False, False
    except ValueError:
        pass

    for s in spots:
        if s in msg:
            return s, False, False

    if len(msg) <= 4 and any(kw in msg for kw in CONFIRM_KEYWORDS):
        return None, False, False

    try:
        llm = get_text_llm()
        prompt = f"""用户在策划文旅剧本游。本地知识库目前收录的景区有：
{chr(10).join(f'- {s}' for s in spots)}

用户说：{msg}

请从用户的话中**抽取**景区名称。

示例：
- "灵运仙境的剧本来一个" → is_spot=true, spot_name="灵运仙境"
- "帮我策划一下苍坡村" → is_spot=true, spot_name="苍坡村"
- "我想做个石桅岩的剧本" → is_spot=true, spot_name="石桅岩"
- "楠溪江有哪些景区" → is_region=true（区域名，不是具体景区）
- "永嘉有什么好玩的" → is_region=true
- "好的" → is_spot=false（无景区名）
- "帮我写个故事" → is_spot=false（无景区名）

规则：
1. 即使用户输入包含指令（如"来一个""写个剧本""策划一下"），也要从中抽取景区名
2. 如果用户明确提到了某个景区名（可以是知识库以外的真实景区），返回 is_spot=true 和 spot_name
3. 如果用户只说了"楠溪江""永嘉"这类区域名（包含多个景区），返回 is_region=true，is_spot=false
4. 如果用户没有提到任何景区名，返回 is_spot=false，is_region=false
5. spot_name 只填景区名称本身，不要带"景区""风景区"等后缀

只输出 JSON：
{{"is_spot": true/false, "spot_name": "景区名或空", "is_region": true/false, "reason": "一句话理由"}}
"""
        invoke = get_json_llm(SpotResolveResult)
        result = invoke([
            SystemMessage(content="你是景区识别助手，从用户输入中抽取景区名称。"),
            HumanMessage(content=prompt),
        ])

        if result.is_region and not result.is_spot:
            return None, True, False

        if result.is_spot and result.spot_name:
            name = result.spot_name.strip()
            if len(name) <= 30 and "\n" not in name and not any(c in name for c in "。！？，、；：\"'（）【】"):
                is_custom = name not in spots
                return name, False, is_custom

        return None, False, False
    except Exception as e:
        print(f"⚠️ 景区识别失败：{e}")
        return None, False, False


def verify_custom_spot(spot_name: str) -> tuple:
    if spot_name in _SPOT_VERIFY_CACHE:
        print(f"✅ 景区验证缓存命中：{spot_name}")
        return _SPOT_VERIFY_CACHE[spot_name]

    try:
        web_info = deepseek_web_search(f"{spot_name} 景区 官方 简介 位置")
    except Exception as e:
        print(f"⚠️ 联网搜索失败：{e}")
        web_info = ""

    if not web_info:
        result = (False, "", "")
        _SPOT_VERIFY_CACHE[spot_name] = result
        return result

    prompt = f"""用户想策划一个叫「{spot_name}」的景区剧本游。

请根据以下搜索结果，判断这个景区是否真实存在：
{web_info}

要求：
1. 只有确认是真实存在的景区（有明确的景区介绍、位置信息），才返回 exists=true
2. 如果搜索结果里没有明确提到该景区，或者是虚构、编造、不存在的名称，返回 exists=false
3. 如果存在，给出标准景区名称和所在地区

只输出 JSON：
{{"exists": true/false, "standard_name": "标准景区名", "location": "所在省市县", "reason": "一句话理由"}}
"""
    try:
        invoke = get_json_llm(SpotVerifyResult)
        result = invoke([
            SystemMessage(content="你是景区核实助手，严格核实景区是否真实存在。"),
            HumanMessage(content=prompt),
        ])
        if result.exists:
            out = (True, result.standard_name or spot_name, result.location)
        else:
            out = (False, "", "")
        _SPOT_VERIFY_CACHE[spot_name] = out
        return out
    except Exception as e:
        print(f"⚠️ 景区核实失败：{e}")
        return False, "", ""


# ===== 主接口 =====
def chat(session_id: str, user_message: str) -> dict:
    if session_id not in SESSIONS:
        greeting, _ = make_greeting()
        SESSIONS[session_id] = {
            "session_id": session_id,
            "messages": [{"role": "assistant", "content": greeting}],
            "user_input": "",
            "script": Script(),
            "stage": "ask_user",
            "reply": greeting,
            "current_node_index": 0,
            "planned_node_titles": [],
            "selected_space_names": [],
            "total_nodes": 0,
            "force_confirm": False,
            "pending_upstream_modify": "",
            "pending_upstream_module": "",
        }
        return make_response(greeting, None, "ask_user", "正在等待您输入景区名称...")

    state = SESSIONS[session_id]
    stage = state["stage"]

    # 用户选景区
    if stage == "ask_user":
        spots = list_available_spots()

        chosen, is_region, is_custom = resolve_spot(user_message, spots)

        if chosen is None and is_region:
            reply = (
                NANXIJIANG_INTRO
                + "\n\n"
                + make_spot_list_reply(spots, prefix="请从楠溪江下的这些具体景区中选一个：")
            )
            state["messages"].append({"role": "user", "content": user_message})
            state["messages"].append({"role": "assistant", "content": reply})
            SESSIONS[session_id] = state
            return make_response(reply, None, "ask_user")

        if chosen is None:
            reply = make_spot_list_reply(
                spots,
                prefix="没能识别出您想策划的景区，请从下面选一个，或输入景区全名："
            )
            state["messages"].append({"role": "user", "content": user_message})
            state["messages"].append({"role": "assistant", "content": reply})
            SESSIONS[session_id] = state
            return make_response(reply, None, "ask_user")

        if is_custom:
            print(f"🔍 检测到自定义景区「{chosen}」，正在联网验证...")
            exists, standard_name, location = verify_custom_spot(chosen)

            if not exists:
                reply = (
                    f"「{chosen}」未能通过联网核实，可能是名称有误或不存在的景区。\n\n"
                    f"请从下方本地知识库中选择，或输入确切的景区全名：\n\n"
                    + make_spot_list_reply(spots)
                )
                state["messages"].append({"role": "user", "content": user_message})
                state["messages"].append({"role": "assistant", "content": reply})
                SESSIONS[session_id] = state
                return make_response(reply, None, "ask_user")

            chosen = standard_name
            print(f"✅ 景区「{chosen}」核实通过（{location}），将启用联网策划")

        # 初始化 project
        state["script"].project.project_id = f"proj_{uuid.uuid4().hex[:12]}"
        state["script"].project.location = chosen
        state["script"].project.name = f"{chosen}·沉浸式剧本游"
        state["script"].project.type = "沉浸式剧本游"
        state["script"].project.duration = "60分钟"
        state["script"].project.players = "2-4人"
        state["script"].project.summary = f"以{chosen}为舞台的沉浸式剧本游"
        state["script"].project.cover = "https://via.placeholder.com/800x450/3498db/ffffff?text=Script+Game"

        skill01 = Skill01_CultureAnalysis()
        state["script"].culture_resources = skill01.run(chosen, "沉浸式剧本游")

        is_local = chosen in spots
        if is_local:
            prefix = f"好的，选择「{chosen}」。正在生成 IP 与世界观，请稍候...\n\n"
        else:
            prefix = (
                f"好的，选择「{chosen}」。\n"
                f"正在识别景区信息，永嘉专属资料正在进一步匹配与补充中……\n\n"
            )

        reply = prefix + run_stage1(state)
        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    # 阶段 1 确认
    if stage == "stage1_confirm":
        intent = judge_intent(user_message, "确认 IP 与世界观")
        if intent == "confirm":
            reply = "正在生成人物与故事梗概，请稍候...\n\n" + run_stage2(state)
        elif intent in ("modify", "add", "remove"):
            reply = "正在根据您的意见调整 IP 与世界观...\n\n" + run_stage1(state, user_preference=user_message)
        else:
            reply = "请回复「确认」进入下一步，或告诉我您想怎么调整 IP 与世界观。"
        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    # 阶段 2 确认
    if stage == "stage2_confirm":
        intent = judge_intent(user_message, "确认人物与故事梗概")
        if intent == "confirm":
            reply = run_stage3_prompt(state)
        elif intent in ("modify", "add", "remove"):
            reply = "正在根据您的意见调整人物与故事...\n\n" + run_stage2(state, user_preference=user_message)
        else:
            reply = "请回复「确认」进入下一步，或告诉我您想怎么调整人物与故事。"
        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    # 阶段 3：用户输入景点
    if stage == "stage3_input_spaces":
        intent = judge_intent(
            user_message,
            "正在选择景点，可以继续追加景点，也可以说'够了'开始生成剧情",
        )
        if intent == "confirm":
            selected = state.get("selected_space_names", [])
            if len(selected) < MIN_SPACES and not state.get("force_confirm"):
                state["force_confirm"] = True
                reply = (
                    f"目前只选了 {len(selected)} 个景点，建议至少选 {MIN_SPACES} 个，"
                    f"这样剧情才有空间变化。\n"
                    f"可以继续输入景点名或序号，或再回复一次「确认」强制开始。\n\n"
                    + _format_stage3_reply(state)
                )
            else:
                if len(selected) < 1:
                    reply = "还没选择任何景点，请先选 1-3 个。\n\n" + _format_stage3_reply(state)
                else:
                    reply = f"好的，共 {len(selected)} 个景点。正在生成剧情结构与绑定...\n\n"
                    reply += run_stage3_generate(state, selected)
                state["force_confirm"] = False
        else:
            reply = run_stage3_handle_input(state, user_message)
            state["force_confirm"] = False

        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    # 阶段 3 确认
    if stage == "stage3_confirm":
        intent = judge_intent(user_message, "确认剧情结构与景点绑定")
        if intent == "confirm":
            reply = "正在生成第 1 个剧情节点...\n\n" + run_stage4_next_node(state)
        elif intent in ("modify", "add", "remove"):
            reply = "请重新输入景点：\n\n" + run_stage3_prompt(state)
        else:
            reply = "请回复「确认」开始生成剧情节点，或告诉我您想调整哪些地方。"
        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    # 阶段 4 每个节点确认
    if stage == "stage4_confirm":
        script: Script = state["script"]
        idx = state.get("current_node_index", 0)
        planned = state.get("planned_node_titles", [])

        intent = judge_intent(user_message, f"确认第 {idx + 1} 个剧情节点")

        if intent == "confirm":
            state["current_node_index"] = idx + 1
            if idx + 1 >= len(planned):
                reply = "所有节点生成完毕，正在生成 NPC 和整体审查...\n\n"
                reply += run_stage5_final(state)
            else:
                reply = f"正在生成第 {idx + 2} 个节点...\n\n"
                reply += run_stage4_next_node(state)
        elif intent in ("modify", "add", "remove"):
            target, reason = judge_modify_target(user_message)
            print(f"🔍 修改对象：{target}（{reason}）")

            if target == "current_node":
                script.plot_nodes.pop()
                reply = "正在根据您的意见调整当前节点...\n\n"
                reply += run_stage4_next_node(state)
            elif target.startswith("upstream_"):
                module_name = UPSTREAM_MODULE_NAMES.get(target, "上游内容")
                reply = (
                    f"您想修改的是「{module_name}」。\n\n"
                    f"修改上游内容会重新生成下游所有内容，"
                    f"包括已生成的 {len(script.plot_nodes)} 个剧情节点。\n\n"
                    f"请回复：\n"
                    f"· 「确认」——执行修改并重新生成\n"
                    f"· 「取消」——放弃修改，继续生成下一个节点"
                )
                state["pending_upstream_modify"] = user_message
                state["pending_upstream_module"] = target
                state["stage"] = "stage4_confirm_upstream"
            else:
                reply = (
                    "请告诉我您想修改的是：\n"
                    "· 当前节点的内容（场景、任务、线索等）\n"
                    "· 或上游的 IP、世界观、角色、故事、剧情结构"
                )
        else:
            reply = "请回复「确认」生成下一个节点，或告诉我您想怎么调整这个节点。"

        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    # 阶段 4：确认是否修改上游
    if stage == "stage4_confirm_upstream":
        intent = judge_intent(user_message, "确认是否修改上游内容")
        module = state.get("pending_upstream_module", "")
        modify_request = state.get("pending_upstream_modify", "")
        script: Script = state["script"]

        if intent == "confirm":
            print(f"🔄 执行上游修改：{module}")

            if module == "upstream_ip":
                clear_downstream(script, module)
                reply = "正在根据您的意见重新生成 IP 与世界观...\n\n"
                reply += run_stage1(state, user_preference=modify_request)
            elif module == "upstream_world":
                clear_downstream(script, module)
                reply = "正在根据您的意见重新生成世界观...\n\n"
                reply += run_stage1(state, user_preference=modify_request)
            elif module == "upstream_characters":
                clear_downstream(script, module)
                reply = "正在根据您的意见重新生成角色与故事...\n\n"
                reply += run_stage2(state, user_preference=modify_request)
            elif module == "upstream_story":
                clear_downstream(script, module)
                reply = "正在根据您的意见重新生成故事主线...\n\n"
                reply += run_stage2(state, user_preference=modify_request)
            elif module == "upstream_structure":
                clear_downstream(script, module)
                selected = [s.name for s in script.spaces]
                reply = "正在根据您的意见重新生成剧情结构...\n\n"
                reply += run_stage3_generate(state, selected)
            else:
                reply = "修改对象未识别，请重新输入修改意见。"
                state["stage"] = "stage4_confirm"

            state["pending_upstream_modify"] = ""
            state["pending_upstream_module"] = ""

        else:
            print(f"↩️ 用户取消修改上游")
            state["pending_upstream_modify"] = ""
            state["pending_upstream_module"] = ""
            state["stage"] = "stage4_confirm"

            idx = state.get("current_node_index", 0)
            planned = state.get("planned_node_titles", [])
            state["current_node_index"] = idx + 1
            if idx + 1 >= len(planned):
                reply = "已取消修改。所有节点生成完毕，正在生成 NPC 和整体审查...\n\n"
                reply += run_stage5_final(state)
            else:
                reply = f"已取消修改。正在生成第 {idx + 2} 个节点...\n\n"
                reply += run_stage4_next_node(state)

        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    # 阶段 5
    if stage == "stage5_confirm":
        intent = judge_intent(user_message, "确认最终策划案")
        if intent == "confirm":
            state["stage"] = "finished"
            reply = "策划案已确认完成。如需重新策划或修改，请开启新会话。"
        elif intent in ("modify", "add", "remove"):
            skill = Skill05_ModifyAnalysis()
            plan = skill.analyze(state["script"], user_message)
            reply = f"已识别修改范围：{plan.scope}，受影响模块：{plan.affected_modules}\n"
            reply += "（当前版本仅演示识别，可后续接入局部重生成）"
        else:
            reply = "如确认无误，回复「确认」结束；如需调整，请直接说出修改意见。"

        state["messages"].append({"role": "user", "content": user_message})
        state["messages"].append({"role": "assistant", "content": reply})
        SESSIONS[session_id] = state
        return make_response(reply, state["script"], state["stage"])

    if stage == "finished":
        reply = "策划案已完成。如需重新策划，请开启新会话。"
        return make_response(reply, state["script"], "finished")

    return make_response("状态异常。", None, "error")
