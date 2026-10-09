"""
分阶段核心 Skills：
- Skill01: 文化资源分析
- Skill02a: IP 与世界观
- Skill02b: 角色与故事梗概
- Skill03a: 候选景点检索
- Skill03b: 剧情结构与景点绑定
- Skill03c: 单个剧情节点生成
- Skill03d: NPC 生成
- Skill04: 剧本审查
- Skill05: 修改影响分析
"""
import json
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage

from schema import (
    Script, IPInfo, WorldInfo, Character, StoryInfo, PlotStructure,
    CultureResource, Space, PlotNode, NPC, Review, ReviewIssue,
)
from prompts import (
    SYSTEM_PROMPT,
    STAGE1_PROMPT, STAGE2_PROMPT, STAGE3_PROMPT,
    STAGE4_SINGLE_NODE_PROMPT, STAGE4_NPCS_PROMPT,
    STAGE3_SPACES_PROMPT,
)
from llm import get_json_llm
from rag import retrieve_multi_dimension, retrieve


class CultureResourceList(BaseModel):
    culture_resources: list[CultureResource] = []


class IPWorldBundle(BaseModel):
    ip: IPInfo
    world: WorldInfo


class CharStoryBundle(BaseModel):
    characters: list[Character] = []
    story: StoryInfo


class SpaceCandidateList(BaseModel):
    spaces: list[Space] = []


class PlotStructureBundle(BaseModel):
    plot_structure: PlotStructure


class SingleNodeBundle(BaseModel):
    plot_node: PlotNode
    node_dialogues: list[dict] = []


class NPCList(BaseModel):
    npcs: list[NPC] = []


class ReviewResult(BaseModel):
    issues: list[ReviewIssue] = []
    passed: bool = False


class ModifyPlan(BaseModel):
    scope: str = ""
    affected_modules: list[str] = []
    reason: str = ""


class Skill01_CultureAnalysis:
    name = "文化资源分析"

    def run(self, location: str, script_type: str) -> list[CultureResource]:
        context = retrieve_multi_dimension(location, script_type)
        prompt = f"""你正在为景区「{location}」分析可用于剧本游的文化资源。

从知识库检索到的资料：
{context}

要求：
1. 提取 3-6 个最适合进入剧本游的文化资源
2. 每个资源标注 authenticity：REAL / ADAPTED / FICTIONAL
3. 每个资源说明它可以在剧本中扮演什么角色
4. 输出 JSON
"""
        invoke = get_json_llm(CultureResourceList)
        result = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.culture_resources


class Skill02a_IPAndWorld:
    name = "IP与世界观"

    def run(self, script: Script, user_preference: str = "") -> IPWorldBundle:
        # 传给 LLM 时只保留 name、description、authenticity，不传 resource_id，
        # 避免 LLM 后续误把编号当成来源引用
        culture_text = "\n".join(
            f"- {c.name}（{c.authenticity}）：{c.description}"
            for c in script.culture_resources
        )
        pref = f"\n用户偏好：{user_preference}" if user_preference else ""
        prompt = STAGE1_PROMPT.format(
            location=script.project.location,
            culture_text=culture_text,
            user_preference=pref,
        )
        invoke = get_json_llm(IPWorldBundle)
        return invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )


class Skill02b_CharactersAndStory:
    name = "角色与故事梗概"

    def run(self, script: Script, user_preference: str = "") -> CharStoryBundle:
        pref = f"\n用户偏好：{user_preference}" if user_preference else ""
        prompt = STAGE2_PROMPT.format(
            ip_name=script.ip.name,
            ip_concept=script.ip.concept,
            world_conflict=script.world.core_conflict,
            player_identity=script.world.player_identity,
            player_goal=script.world.player_goal,
            user_preference=pref,
        )
        invoke = get_json_llm(CharStoryBundle)
        return invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )


class Skill03a_ListSpaces:
    name = "候选景点检索"

    def run(self, script: Script) -> list[Space]:
        context = retrieve_multi_dimension(script.project.location, "空间")
        prompt = STAGE3_SPACES_PROMPT.format(
            location=script.project.location,
            ip_concept=script.ip.concept,
            context=context,
        )
        invoke = get_json_llm(SpaceCandidateList)
        result = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.spaces


class Skill03b_PlotStructure:
    name = "剧情结构与景点绑定"

    def run(self, script: Script, selected_spaces: list[Space], total_nodes: int, user_preference: str = "") -> PlotStructure:
        spaces_text = json.dumps(
            [s.model_dump() for s in selected_spaces], ensure_ascii=False
        )
        pref = user_preference.strip() if user_preference else "（无）"
        prompt = STAGE3_PROMPT.format(
            ip_name=script.ip.name,
            selling_point=script.ip.selling_point,
            story_synopsis=script.story.synopsis,
            player_goal=script.world.player_goal,
            space_count=len(selected_spaces),
            total_nodes=total_nodes,
            spaces_text=spaces_text,
            user_preference=pref,
        )
        invoke = get_json_llm(PlotStructureBundle)
        result = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.plot_structure



class Skill03c_SingleNode:
    name = "单个剧情节点生成"

    def run(
        self,
        script: Script,
        node_index: int,
        total_nodes: int,
        node_title: str,
        previous_nodes: list[PlotNode],
        user_preference: str = "",
        previous_node_json: str = "",
        character_usage: dict[str, int] | None = None,
    ) -> tuple[PlotNode, list[dict]]:
        space_text = json.dumps(
            [s.model_dump() for s in script.spaces], ensure_ascii=False
        )
        culture_text = "\n".join(
            f"- {c.name}（{c.authenticity}）\n"
            f"  内容：{c.description}\n"
            f"  来源：{c.source}"
            for c in script.culture_resources
        )

        # 角色名单：每个人物最多在两个剧情节点中出场。
        usage = character_usage or {}
        characters_text = "\n".join(
            f"- {c.name}（{c.role}）：{c.function}；已使用 {usage.get(c.name, 0)}/2 次"
            for c in script.characters
            if usage.get(c.name, 0) < 2
        )
        if not characters_text:
            characters_text = "（没有剩余可用人物；本节点 node_dialogues 必须输出空列表）"

        if previous_nodes:
            prev_summary = [
                {
                    "node_id": n.node_id,
                    "title": n.title,
                    "space_id": n.space_id,
                    "scene_desc": (n.scene.get("description", "") if isinstance(n.scene, dict) else "")[:50],
                    "objective": (n.task.objective or "")[:50],
                }
                for n in previous_nodes
            ]
            prev_text = json.dumps(prev_summary, ensure_ascii=False, indent=2)
        else:
            prev_text = "（无，这是第一个节点）"

        pref = user_preference.strip() if user_preference else "（无）"
        prev_node_text = previous_node_json if previous_node_json else "（无，这是首次生成）"

        prompt = STAGE4_SINGLE_NODE_PROMPT.format(
            node_index=node_index,
            total_nodes=total_nodes,
            ip_name=script.ip.name,
            selling_point=script.ip.selling_point,
            story_synopsis=script.story.synopsis,
            player_goal=script.world.player_goal,
            node_title=node_title,
            is_last_node="是" if node_index == total_nodes else "否",
            spaces_text=space_text,
            culture_text=culture_text,
            characters_text=characters_text,
            previous_nodes=prev_text,
            user_preference=pref,
            previous_node_json=prev_node_text,
        )
        invoke = get_json_llm(SingleNodeBundle)
        result = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.plot_node, result.node_dialogues





class Skill03d_NPCs:
    name = "NPC生成"

    def run(self, script: Script) -> list[NPC]:
        characters_json = json.dumps(
            [c.model_dump() for c in script.characters], ensure_ascii=False
        )
        prompt = STAGE4_NPCS_PROMPT.format(
            ip_name=script.ip.name,
            characters_json=characters_json,
            spaces_json=json.dumps(
                [s.model_dump() for s in script.spaces], ensure_ascii=False
            ),
            nodes_json=json.dumps(
                [n.model_dump() for n in script.plot_nodes], ensure_ascii=False
            ),
        )
        invoke = get_json_llm(NPCList)
        result = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.npcs


class Skill04_Audit:
    name = "剧本审查"

    def run(self, script: Script) -> ReviewResult:
        # 只传审查需要的字段，避免完整 script 在节点多时超 token。
        # 每个节点摘要控制在 200 字符以内。
        space_map = {s.space_id: s.name for s in script.spaces}

        characters_summary = [
            {"id": c.character_id, "name": c.name, "role": c.role}
            for c in script.characters
        ]

        nodes_summary = []
        for n in script.plot_nodes:
            nodes_summary.append({
                "node_id": n.node_id,
                "title": n.title,
                "space_id": n.space_id,
                "space_name": space_map.get(n.space_id, "?"),
                "objective": (n.task.objective or "")[:60],
                "interaction_type": n.interaction.type,
                "clue_sources": [c.source for c in n.clues],
                "culture_sources": [c.source for c in n.culture],
            })

        npcs_summary = [
            {
                "npc_id": npc.npc_id,
                "name": npc.name,
                "role": npc.role,
                "background": (npc.background or "")[:80],
                "space_ids": npc.space_ids,
                "plot_node_ids": npc.plot_node_ids,
            }
            for npc in script.npcs
        ]

        acts_summary = [
            {"act": a.get("act", ""), "node_titles": a.get("node_titles", [])}
            for a in script.plot_structure.acts
        ]

        summary = {
            "project": {
                "location": script.project.location,
                "players": script.project.players,
                "duration": script.project.duration,
            },
            "characters": characters_summary,
            "plot_structure_acts": acts_summary,
            "spaces": [{"space_id": s.space_id, "name": s.name} for s in script.spaces],
            "plot_nodes": nodes_summary,
            "npcs": npcs_summary,
        }

        summary_json = json.dumps(summary, ensure_ascii=False, indent=2)

        prompt = f"""你是剧本游审查专家。请审查以下剧本项目。

项目摘要 JSON：
{summary_json}

从以下 6 个维度检查：
1. 世界观一致性（角色名称是否重名、同一人物的身份是否前后一致、NPC 的 background 是否引用了 characters 中不存在的角色）
2. 剧情逻辑（plot_structure_acts 的 node_titles 是否与 plot_nodes 的 title 一一对应）
3. 游戏可玩性（project.players 与任务是否匹配，任务是否可完成）
4. 空间可行性（每个节点的 space_id 是否在 spaces 中，节点是否分布在不同空间，动线是否重复）
5. 文化真实性（plot_nodes 的 culture_sources 是否为文字来源，不是 CR 编号）
6. 实施可行性

要求：
- 每个 issue 包含 dimension、severity、description、location、suggestion
- 最多输出 5 条 issue
- 输出 JSON
"""
        invoke = get_json_llm(ReviewResult)
        return invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )

class Skill05_ModifyAnalysis:
    name = "修改影响分析"

    def analyze(self, script: Script, user_request: str) -> ModifyPlan:
        summary = f"IP：{script.ip.name}\n世界观：{script.world.core_conflict}\n剧情结构幕数：{len(script.plot_structure.acts)}\n节点数：{len(script.plot_nodes)}"
        prompt = f"""用户对当前剧本提出了修改需求。

当前剧本概要：
{summary}

用户修改需求：
{user_request}

请判断：
1. scope：local / module / directional
2. affected_modules：从 ["ip", "world", "characters", "story", "plot_structure", "plot_nodes", "npcs"] 中选
3. reason：一句话理由

输出 JSON。
"""
        invoke = get_json_llm(ModifyPlan)
        return invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
