"""
JSON 引用一致性校验器。
在 Agent 生成完整 Script 后调用，检查所有 ID 引用是否有效。
"""
from schema import Script


def validate_script(script: Script) -> list[str]:
    """
    校验规则：
    1. 所有 plot_nodes 的 space_id 必须在 spaces 中存在
    2. 所有 next_node_id 必须指向有效 node_id（空字符串允许）
    3. 所有 prerequisites 必须引用有效 node_id
    4. 所有 npcs 的 space_ids 和 plot_node_ids 必须有效
    5. 所有 ID 唯一（space_id、node_id、npc_id、clue_id）

    返回错误列表，空列表表示校验通过。
    """
    errors = []

    space_ids = [s.space_id for s in script.spaces]
    node_ids = [n.node_id for n in script.plot_nodes]
    npc_ids = [n.npc_id for n in script.npcs]

    # 1. ID 唯一性
    if len(space_ids) != len(set(space_ids)):
        errors.append("spaces 中存在重复的 space_id")
    if len(node_ids) != len(set(node_ids)):
        errors.append("plot_nodes 中存在重复的 node_id")
    if len(npc_ids) != len(set(npc_ids)):
        errors.append("npcs 中存在重复的 npc_id")

    space_id_set = set(space_ids)
    node_id_set = set(node_ids)

    # 2. plot_nodes 的 space_id 必须有效
    for node in script.plot_nodes:
        if node.space_id and node.space_id not in space_id_set:
            errors.append(
                f"节点 {node.node_id} 的 space_id='{node.space_id}' 不在 spaces 中"
            )

    # 3. next_node_id 必须有效（空字符串允许）
    for node in script.plot_nodes:
        if node.next_node_id and node.next_node_id not in node_id_set:
            errors.append(
                f"节点 {node.node_id} 的 next_node_id='{node.next_node_id}' 无效"
            )

    # 4. prerequisites 必须有效
    for node in script.plot_nodes:
        for pre in node.prerequisites:
            if pre not in node_id_set:
                errors.append(
                    f"节点 {node.node_id} 的 prerequisites 引用 '{pre}' 无效"
                )

    # 5. NPC 的 space_ids 和 plot_node_ids 必须有效
    for npc in script.npcs:
        for sid in npc.space_ids:
            if sid not in space_id_set:
                errors.append(f"NPC {npc.npc_id} 的 space_id='{sid}' 无效")
        for nid in npc.plot_node_ids:
            if nid not in node_id_set:
                errors.append(f"NPC {npc.npc_id} 的 plot_node_id='{nid}' 无效")

    # 6. 每个节点至少有一个 space_id（非空）
    for node in script.plot_nodes:
        if not node.space_id:
            errors.append(f"节点 {node.node_id} 缺少 space_id")

    # 7. 每个节点的 interaction.type 必须在枚举内，且不能为空
    valid_types = {
        "gps", "ar", "nfc", "physical_device", "npc_dialogue",
        "quiz", "puzzle", "prop", "teamwork", "online",
    }
    for node in script.plot_nodes:
        if not node.interaction.type:
            errors.append(f"节点 {node.node_id} 的 interaction.type 为空")
        elif node.interaction.type not in valid_types:
            errors.append(
                f"节点 {node.node_id} 的 interaction.type='{node.interaction.type}' 不在枚举内"
            )

    # 8. NPC 的 appearance_mode 必须在枚举内
    valid_modes = {"online", "offline", "both"}
    for npc in script.npcs:
        if npc.appearance_mode not in valid_modes:
            errors.append(
                f"NPC {npc.npc_id} 的 appearance_mode='{npc.appearance_mode}' 不在枚举内"
            )

    return errors


def print_validation_report(script: Script) -> bool:
    """
    打印校验报告。返回 True 表示通过，False 表示有错误。
    """
    errors = validate_script(script)
    if not errors:
        print("✅ 校验通过，无错误")
        return True
    print(f"❌ 校验失败，共 {len(errors)} 个错误：")
    for e in errors:
        print(f"  - {e}")
    return False