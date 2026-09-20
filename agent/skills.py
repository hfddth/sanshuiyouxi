"""
核心 Skills：
- Skill01：永嘉文旅资源分析
- Skill02：文旅IP策划
- Skill03：沉浸式剧本游设计
- Skill04：剧本审查
- Skill05：修改影响分析
"""
import json
from pydantic import BaseModel
from langchain_core.messages import HumanMessage, SystemMessage

from schema import (
    Script, IPInfo, WorldInfo, Character, StoryInfo,
    CultureResource, Space, PlotNode, NPC, Review, ReviewIssue,
)
from prompts import SYSTEM_PROMPT
from llm import get_json_llm
from rag import retrieve_multi_dimension


class CultureResourceList(BaseModel):
    culture_resources: list[CultureResource] = []


class IPBundle(BaseModel):
    ip: IPInfo
    world: WorldInfo
    characters: list[Character] = []
    story: StoryInfo


class SpaceList(BaseModel):
    spaces: list[Space] = []


class PlotNodeList(BaseModel):
    plot_nodes: list[PlotNode] = []


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
    name = "永嘉文旅资源分析"

    def run(self, location: str, script_type: str) -> list[CultureResource]:
        context = retrieve_multi_dimension(location, script_type)
        prompt = f"""你正在为景区「{location}」分析可用于剧本游的文化资源。

从知识库检索到的资料：
{context}

要求：
1. 提取 3-6 个最适合进入剧本游的文化资源
2. 每个资源标注 authenticity：
   - REAL：真实文化，必须能追溯到资料
   - ADAPTED：基于真实文化的艺术改编
   - FICTIONAL：完全虚构
3. 每个资源说明它可以在剧本中扮演什么角色
4. 输出 JSON
"""
        invoke = get_json_llm(CultureResourceList)
        result: CultureResourceList = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.culture_resources


class Skill02_IPPlanning:
    name = "文旅IP策划"

    def run(self, script: Script, user_preference: str = "") -> IPBundle:
        culture_text = "\n".join(
            f"- {c.name}（{c.authenticity}）：{c.description}"
            for c in script.culture_resources
        )
        pref_line = f"\n用户偏好：{user_preference}" if user_preference else ""
        prompt = f"""你正在为景区「{script.project.location}」策划剧本游 IP。{pref_line}

可用文化资源：
{culture_text}

请生成：
1. IP 方向（name、concept、positioning、selling_point、target_audience、emotional_value、visual_style）
2. 世界观（time_setting、world_rules、event_cause、core_conflict、player_identity、player_goal、final_goal、culture_relation）
3. 角色列表（玩家、主角、NPC、对立角色、支持角色），每个角色必须有 function
4. 故事主线（synopsis、background、event、player_intervention、player_goal、conflict_escalation、info_reveal、climax、ending）

要求：
- 世界观必须区分真实文化基础和虚构剧情
- 角色必须服务于剧情或游戏功能
- 故事必须有清晰的因果链
- 输出 JSON
"""
        invoke = get_json_llm(IPBundle)
        result: IPBundle = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result


class Skill03_ScriptDesign:
    name = "沉浸式剧本游设计"

    def run_spaces(self, script: Script) -> list[Space]:
        context = retrieve_multi_dimension(
            script.project.location, script.project.type
        )
        prompt = f"""根据以下资料，为剧本「{script.project.name}」生成真实空间列表。

IP 名称：{script.ip.name}
IP 概念：{script.ip.concept}

知识库资料：
{context}

要求：
1. 每个 space 必须有 space_id（S01、S02……）、name、type、description
2. space 必须是资料中真实存在的地点
3. 输出 JSON
"""
        invoke = get_json_llm(SpaceList)
        result: SpaceList = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.spaces

    def run_nodes(self, script: Script) -> list[PlotNode]:
        context = retrieve_multi_dimension(
            script.project.location, script.project.type
        )
        culture_text = "\n".join(
            f"- {c.resource_id} {c.name}（{c.authenticity}）" for c in script.culture_resources
        )
        spaces_text = json.dumps(
            [s.model_dump() for s in script.spaces], ensure_ascii=False
        )
        prompt = f"""为剧本「{script.project.name}」生成剧情节点 plot_nodes。

IP 概念：{script.ip.concept}
故事主线：
{script.story.synopsis}

玩家目标：
{script.world.player_goal}

可用真实空间：
{spaces_text}

可用文化资源：
{culture_text}

【硬性要求，必须严格遵守】
1. 节点数量必须为 4 到 6 个，推荐 5 个
2. 每个节点必须绑定一个 space_id
3. 通过 next_node_id 形成推进关系
4. 每个节点的 culture 字段最多 2 条，每条只填 name、authenticity、source、integration 四个字段
5. 每个节点的 clues 最多 2 条
6. 每个节点的 rewards 最多 1 条
7. opening_narration 不超过 100 字
8. closing_narration 不超过 80 字
9. scene.description 不超过 80 字
10. scene.plot 不超过 80 字
11. task.objective 不超过 60 字
12. task.completion_condition 不超过 50 字
13. task.player_actions 最多 3 条，每条不超过 30 字
14. interaction.description 不超过 40 字

node_id 命名规则：
- 主节点 N01、N02、N03、N04、N05
- 所有 node_id 必须唯一
- sequence 从 1 开始递增

next_node_id 规则：
- 必须引用已存在的 node_id
- 最后一个节点的 next_node_id 留空字符串

prerequisites 规则：
- 只能填写已存在的 node_id
- 第一个节点的 prerequisites 为空列表
- 后续节点的 prerequisites 只填前一个节点 ID

输出 JSON 数组，只输出 JSON，不要任何额外解释。
"""
        invoke = get_json_llm(PlotNodeList)
        result: PlotNodeList = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result.plot_nodes

    def run_npcs(self, script: Script) -> list[NPC]:
        prompt = f"""为剧本「{script.project.name}」生成 NPC 列表。

已知空间：
{json.dumps([s.model_dump() for s in script.spaces], ensure_ascii=False)}

已知剧情节点：
{json.dumps([n.model_dump() for n in script.plot_nodes], ensure_ascii=False)}

【硬性要求】
1. NPC 数量控制在 2-4 个
2. 每个 NPC 必须有唯一 npc_id
3. 必须有 function（提供信息/触发任务/推进剧情/提供线索/制造误导）
4. appearance_mode 只能是 online / offline / both
5. space_ids 和 plot_node_ids 必须引用有效 ID
6. personality、background、appearance 各不超过 80 字
7. 输出 JSON 数组，只输出 JSON
"""
        invoke = get_json_llm(NPCList)
        result: NPCList = invoke(
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
1. 世界观一致性（时间、身份、规则是否冲突）
2. 剧情逻辑（因果关系、信息传递是否合理）
3. 游戏可玩性（目标是否明确、谜题是否可解、是否存在死路）
4. 空间可行性（地点是否存在于 spaces、路线是否合理）
5. 文化真实性（culture 是否有 source 支持、是否把虚构当事实）
6. 实施可行性（互动类型是否必要、是否技术堆砌）

要求：
- 每个 issue 包含 dimension、severity（high/medium/low）、description、location、suggestion
- 最多输出 5 条 issue
- 如果没有任何问题，passed = true
- 输出 JSON
"""
        invoke = get_json_llm(ReviewResult)
        result: ReviewResult = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result


class Skill05_ModifyAnalysis:
    name = "修改影响分析"

    def analyze(self, script: Script, user_request: str) -> ModifyPlan:
        summary = f"""IP：{script.ip.name} - {script.ip.concept}
世界观：{script.world.core_conflict}
角色：{', '.join([c.name for c in script.characters])}
故事：{script.story.synopsis}
剧情节点数：{len(script.plot_nodes)}
NPC数：{len(script.npcs)}
文化资源：{', '.join([c.name for c in script.culture_resources])}"""
        prompt = f"""用户对当前剧本提出了修改需求。

当前剧本概要：
{summary}

用户修改需求：
{user_request}

请判断：
1. scope（修改范围）：
   - local：只改某个角色、某个线索、某个 NPC，不动其他
   - module：改某一类模块（如只改任务难度、只改某段剧情）
   - directional：改整体风格方向（如"换成悬疑"、"改成东方奇幻"）

2. affected_modules：受影响需要重新生成的模块列表，只能从以下选：
   ["ip", "world", "characters", "story", "plot_nodes", "npcs"]
   注意：spaces 和 culture_resources 是客观资料，一般不重新生成。

3. reason：判断理由（一句话）

输出 JSON。
"""
        invoke = get_json_llm(ModifyPlan)
        result: ModifyPlan = invoke(
            [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
        )
        return result