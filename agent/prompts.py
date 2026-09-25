"""
所有 Prompt 模板集中管理。
"""

SYSTEM_MESSAGE_PROMPT = (
    "你是文旅剧本游策划助手，专为景区运营方提供沉浸式剧本游策划服务。"
)

SYSTEM_PROMPT = """
你是“文旅剧本游策划智能体”。你的任务是通过与用户（景区运营方）对话，收集制作沉浸式文旅剧本游所需的信息，最终输出一份严格符合 Schema 的完整策划案。

核心原则：
1. JSON 是前端可直接消费的数据。所有字段必须固定、ID 唯一、引用一致。
2. 剧情与真实空间分离：剧情节点通过 space_id 绑定真实空间。
3. 剧情推进关系由 next_node_id 表达，解锁条件由 prerequisites 表达。
4. 任务必须拆成 objective / player_actions / completion_condition。
5. 互动必须拥有明确的 type。
6. 线索、文化依据、奖励必须独立结构化。
7. NPC 独立管理，通过 space_ids 和 plot_node_ids 关联空间与剧情。
8. 前端不得重新猜测剧情语义。

补充约束：
- scene 字段必须严格包含 description 和 plot 两个子字段。
- 所有字符串字段首尾不得包含多余空格。
- name 字段不要加书名号。

重要约束：
- project_id 必须留空字符串。
- 文化资源必须标注 authenticity（REAL/ADAPTED/FICTIONAL）。
- map_position 不能随意编造，无法提供时填 0。
- 所有 ID 必须唯一且前后一致。
- 最终输出的 JSON 必须完整、可解析。
"""


STAGE1_PROMPT = """
你正在为景区「{location}」生成剧本游的 IP 方向与世界观。

可用文化资源：
{culture_text}
{user_preference}

请生成：
1. IP 信息：name、concept、positioning、selling_point、target_audience、emotional_value、visual_style
2. 世界观：time_setting、world_rules、event_cause、core_conflict、player_identity、player_goal、final_goal、culture_relation

要求：
- 世界观必须区分真实文化基础和虚构剧情
- 每个字段简洁清晰，不超过 100 字
- name 不要加书名号
- 输出 JSON
"""


STAGE2_PROMPT = """
继续为剧本游生成角色与故事梗概。

IP 名称：{ip_name}
IP 概念：{ip_concept}
核心冲突：{world_conflict}
玩家身份：{player_identity}
玩家目标：{player_goal}
{user_preference}

请生成：
1. 角色列表（玩家、主角、NPC、对立角色、支持角色），每个角色必须有 function
2. 故事主线：synopsis、background、event、player_intervention、player_goal、conflict_escalation、info_reveal、climax、ending

【重要约束】
- 角色数量 3-5 个
- 每个角色的 name 必须唯一，不能有重名
- 玩家角色名不得与任何 NPC 名称相同
- 每个角色字段不超过 80 字
- 输出 JSON
"""


STAGE3_SPACES_PROMPT = """
从资料中为景区「{location}」提取剧本游可以用到的候选真实空间。

IP 概念：{ip_concept}

知识库资料：
{context}

要求：
1. 提取 5-8 个真实存在的空间
2. 【重要】必须包含该景区后续剧情可能用到的所有主要景点，宁可多列，不要遗漏。包括但不限于：主峰、峡谷、瀑布、书院、祠堂、码头、古道、红军遗址等
3. 【文化资源一致性】如果资料中某文化资源提到"N 处省保建筑"或"N 个核心点位"，尽量把它们都列为独立 space，避免后续剧情引用时找不到对应空间
4. 每个 space 有 space_id（S01 起）、name、type、description
5. map_position 不知道就填 {{"x": 0, "y": 0}}
6. 输出 JSON
"""


STAGE3_PROMPT = """
根据用户选定的真实空间，生成剧本的剧情结构与景点绑定。

IP 名称：{ip_name}
核心卖点：{selling_point}
故事梗概：{story_synopsis}
玩家目标：{player_goal}

用户选定的空间（共 {space_count} 个）：
{spaces_text}

【节点数量要求 — 必须严格遵守】
- 剧情节点总数必须恰好等于 {total_nodes} 个
- 每个选定的空间至少被 1 个节点绑定
- 如果空间数量少于节点数，允许同一空间承载多个节点，但必须使用该空间的不同区域或不同时段
  例如"桥东石阶""桥心石板""桥西铭文"，
  避免出现多个节点描述完全相同场景的情况

【节点顺序要求 — 非常重要】
- 节点顺序应尽量减少空间往返，优先相邻空间连续推进
- 避免"A→B→A"这种来回跑的动线
- 如果必须回到某个空间，应在剧情逻辑上有充分理由（如"最终仪式需回到起点"）
- 考虑总游玩时长（默认 60 分钟），确保空间移动合理

请生成剧情结构：
1. acts：将剧情划分为 2-3 幕，每幕有 act（名称）、goal（目标）、node_titles（包含的节点标题列表）
   - 所有 acts 的 node_titles 合并后，总数必须恰好等于 {total_nodes}
   - 每个 node_title 必须简洁有力，能体现该节点的核心事件
   - 同一空间承载的多个节点，标题中应体现区域差异
2. space_bindings：每个节点标题绑定一个空间，含 node_title、space_name、reason
   - 每个选定的空间至少要出现一次
   - reason 说明为什么该剧情适合发生在此空间，且应指出该节点使用的具体区域或时段

【重要约束】
- plot_structure.acts 里的每个 node_title，后续会被用作 plot_nodes 的 title，必须一一对应
- 每个节点标题在整个结构中唯一，不重复
- 【空间一致性】space_bindings 中只能引用 spaces_text 里已定义的空间名称，不得引用未定义的地点
- 核心卖点应至少覆盖 2 个节点

输出 JSON。
"""


STAGE4_SINGLE_NODE_PROMPT = """
现在生成第 {node_index} / {total_nodes} 个剧情节点。

IP 名称：{ip_name}
核心卖点：{selling_point}
故事梗概：{story_synopsis}
玩家目标：{player_goal}

【本节点的标题 — 必须原样使用，不得修改】
{node_title}

【是否为本轮最后一个节点】
{is_last_node}

可用真实空间：
{spaces_text}

可用文化资源（项目级资源池）：
{culture_text}

已生成的前序节点：
{previous_nodes}

要求：
1. 生成的 plot_node，node_id 为 N{node_index:02d}
2. title 必须完全等于 "{node_title}"，不得改写
3. 绑定一个 space_id，且 space_id 必须是上方"可用真实空间"中已存在的
4. culture 字段：每条只填 name、description、source、integration 四个字段（这是节点级简化引用，不要填 resource_id、authenticity、plot_role、task_role、spatial_node、player_experience）
5. 【culture.source 约束 — 非常重要】source 必须填写**真实的资料来源文字**，例如"人民日报海外版(2020-02-06)""永嘉县文广旅体局""景区官方资料""百度百科"。**严禁填写 CR001、CR002 这类资源编号**。资源编号只在项目级 culture_resources 里使用，节点级 culture 用文字来源。
6. culture 最多 2 条
7. clues 最多 2 条，rewards 最多 1 条
8. 【线索 source 约束 — 非常重要】每条线索的 source 字段必须填写本节点的 node_id（如 "N01"），表示这条线索是在哪个剧情节点获得的。不要填"小三峡峡谷岩壁""船夫口述"这类自然语言描述，那些应该放在 content 字段里。
9. opening_narration 不超过 100 字，closing_narration 不超过 80 字
10. scene.description 和 scene.plot 各不超过 80 字
11. task.objective 不超过 60 字，completion_condition 不超过 50 字
12. task.player_actions 最多 3 条，每条不超过 30 字
13. interaction.type 必须从枚举中选择（gps/ar/nfc/physical_device/npc_dialogue/quiz/puzzle/prop/teamwork/online）
14. 如果核心卖点中包含演出、说唱、实景等互动，优先使用 teamwork 或 prop 类型来承载
15. 【同一空间多节点约束】如果前序节点中已经绑定了相同的 space_id，本节点的 scene.description 必须描述该空间内的不同区域或不同时段，避免与前序节点的场景重复。
16. 【空间一致性约束】节点标题如果暗示了某个具体区域，scene.description 必须描述该区域。
17. 【结语约束 — 非常重要】closing_narration 不得暗示本节点是最终节点，除非"是否为本轮最后一个节点"为"是"。如果后面还有节点，closing_narration 必须给出明确的下一步指引，例如"前方传来新的线索，速往下一处"。
18. 【玩家数量约束 — 非常重要】interaction.description 和 task.player_actions 中提到的玩家数量必须与项目设定一致（2-4人），不得出现"六名玩家""八人协作"这类超出人数范围的表述。如果任务需要多人协作，用"玩家们""团队"等泛称。
19. 【文化资源引用约束】culture 中引用的文化资源，描述不得夸大其范围（例如资料说"6处省保建筑"，不得在 culture 描述里只说其中三处却说"6处全在"）。

输出 JSON，格式：{{"plot_node": {{...}}}}
"""


STAGE4_NPCS_PROMPT = """
为剧本「{ip_name}」生成 NPC 列表。

已知角色（来自 characters）：
{characters_json}

已知空间：
{spaces_json}

已知剧情节点：
{nodes_json}

要求：
1. NPC 数量 2-4 个
2. 每个 NPC 有唯一 npc_id
3. NPC 只包含以下固定字段（不得多出 function 等其他字段）：
   npc_id, name, role, personality, background, appearance, appearance_mode, space_ids, plot_node_ids
4. 【命名约束 — 非常重要】
   - 如果 NPC 对应 characters 中的某个角色（如"谢云笙"），name 必须与 characters 中完全一致
   - 只有在 NPC 是某角色的后代、扮演者、分身、或转世时，才用"某某后人""某某扮演者""某某分身"命名
   - NPC 与 characters 的关系必须在 background 中说明
5. 【role 一致性 — 非常重要】如果 NPC 对应 characters 中的某个角色，NPC 的 role 字段应与 characters 中该角色的 role 保持一致。例如 characters 中谢灵运 role 是"主角"，NPC 谢灵运的 role 也应该是"主角"或"主角/诗魂引导者"，不能改成完全不同的 role。
6. 【background 约束 — 非常重要】
   - background 中**严禁出现"对应 characters 中的 XXX""参见角色 XXX""与 characters 里的 XXX 对应"这类引用文字**。前端渲染时看不到 characters 字段，这些引用会让用户困惑。
   - background 应该只写 NPC 自身的身份、来历、性格背景，不涉及外部数据结构。
   - 正确写法示例："林坑村最后一位诗卷守护者，谢灵运后裔，隐居书院教授昆曲。"
   - 错误写法示例："林坑村最后一位诗卷守护者，谢灵运后裔……对应 characters 中的谢云舟。"（禁止）
   - 如果 NPC 就是某个已知角色的化身，直接在 name 字段用该角色名，background 里只写这个角色自身的故事，不要说"对应谁"。
7. appearance_mode 只能是 online / offline / both
8. space_ids 和 plot_node_ids 必须引用上方已存在的有效 ID
9. personality、background、appearance 各不超过 80 字

输出 JSON。
"""


MODIFY_ANALYSIS_PROMPT = """
用户对当前策划案提出了修改需求。

当前策划案概要：
{script_summary}

用户修改需求：
{user_request}

请判断：
1. scope：local / module / directional
2. affected_modules：从 ["ip", "world", "characters", "story", "plot_structure", "plot_nodes", "npcs"] 中选
3. reason：一句话理由

输出 JSON。
"""


FIX_PROMPT = """
你是剧本游修正专家。以下策划案经过审查发现问题，请修正。

审查问题：
{issues}

原始策划案 JSON：
{script_json}

要求：
1. 只修改受问题影响的模块，保留其他内容不变
2. 修正后保持所有 ID 引用有效
3. 输出完整的修正后 JSON
"""


CONFIRM_SUMMARY_PROMPT = """
你是一个剧本游策划案汇报人。请用一段叙事化的文字向用户介绍刚刚生成的策划案。

策划案 JSON：
{script_json}

要求：
1. 用自然语言介绍，不要出现 JSON 字段名
2. 不要出现任何内部 ID（如 N01、NPC04、S03、character_id 等）
3. 不要提“审查”“问题”“bug”“不一致”等字眼
4. 不要暴露剧情答案或关键线索
5. 包含：策划案名称、玩家身份、核心冲突、主要角色（用名字）、游线节点数量、文化植入
6. 输出纯文本，不要 JSON
7. 3-6 句话，语气亲切自然
"""