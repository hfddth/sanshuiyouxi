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

    def run(self, script: Script, selected_spaces: list[Space], total_nodes: int) -> PlotStructure:
        spaces_text = json.dumps(
            [s.model_dump() for s in selected_spaces], ensure_ascii=False
        )
        prompt = STAGE3_PROMPT.format(
            ip_name=script.ip.name,
            selling_point=script.ip.selling_point,
            story_synopsis=script.story.synopsis,
            player_goal=script.world.player_goal,
            space_count=len(selected_spaces),
            total_nodes=total_nodes,
            spaces_text=spaces_text,
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
    ) -> PlotNode:
        space_text = json.dumps(
            [s.model_dump() for s in script.spaces], ensure_ascii=False
        )
        # 【关键改动】不再把 resource_id 传给 LLM。
        # 只传 name、authenticity、description、source（文字的来源），
        # 让 LLM 在生成 plot_node.culture 的 source 字段时，
        # 只能照抄 culture_resources 里已有的文字来源，不会误用 CR 编号。
        culture_text = "\n".join(
            f"- {c.name}（{c.authenticity}）\n"
            f"  内容：{c.description}\n"
            f"  来源：{c.source}"
            for c in script.culture_resources
        )
        prev_text = (
            json.dumps(
                [n.model_dump() for n in previous_nodes], ensure_ascii=False
            )
            if previous_nodes
            else "（无，这是第一个节点）"
        )
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
            previous_nodes=prev_text,
        )
        invoke = get_json_llm(SingleNodeBundle)
        result = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.plot_node


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
        prompt = f"""你是剧本游审查专家。请审查以下剧本项目。

完整项目 JSON：
{script.model_dump_json(indent=2)}

从以下 6 个维度检查：
1. 世界观一致性（角色名称是否重名、同一人物的身份是否前后一致、NPC 的 background 是否引用了 characters 中不存在的角色）
2. 剧情逻辑（plot_structure.acts 的 node_titles 是否与 plot_nodes 的 title 一一对应）
3. 游戏可玩性（玩家数量是否与 project.players 一致，任务是否可完成）
4. 空间可行性（每个节点绑定的 space_id 是否真实存在，节点是否分布在不同空间，动线是否重复）
5. 文化真实性（culture.source 是否为文字来源而非 CR 编号）
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