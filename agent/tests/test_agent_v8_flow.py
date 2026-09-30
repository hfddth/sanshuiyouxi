from types import SimpleNamespace

import agent as flow
from schema import PlotNode, Script, Space


def test_last_node_card_prompts_final_review():
    node = PlotNode(node_id="N01", title="终章")

    regular = flow.format_node_card(node, "古村", 1, 2)
    final = flow.format_node_card(node, "古村", 2, 2, is_last=True)

    assert "生成下一个节点" in regular
    assert "最终审查并输出完整策划案" in final
    assert "生成下一个节点" not in final


def test_remove_target_can_fall_back_to_candidate_number():
    candidates = [
        SimpleNamespace(name="入口"),
        SimpleNamespace(name="古街"),
        SimpleNamespace(name="书院"),
    ]

    assert flow._parse_remove_targets("删除3", ["书院"], candidates) == ["书院"]


def test_three_selected_spaces_advance_to_first_node(monkeypatch):
    script = Script(
        spaces=[
            Space(space_id="S01", name="入口"),
            Space(space_id="S02", name="古街"),
            Space(space_id="S03", name="书院"),
            Space(space_id="S04", name="码头"),
        ]
    )
    state = {"script": script, "selected_space_names": []}
    monkeypatch.setattr(flow, "run_stage3_generate", lambda *_args, **_kwargs: "STRUCTURE")
    monkeypatch.setattr(flow, "run_stage4_next_node", lambda *_args, **_kwargs: "NODE-1")

    reply = flow.run_stage3_handle_input(state, "1,2,3")

    assert state["selected_space_names"] == ["入口", "古街", "书院"]
    assert "STRUCTURE" in reply
    assert "NODE-1" in reply
