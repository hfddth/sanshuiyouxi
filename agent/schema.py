from pydantic import BaseModel, Field
from typing import Literal, List


class Project(BaseModel):
    project_id: str = ""
    name: str = ""
    location: str = ""
    type: str = ""
    players: str = ""
    summary: str = ""


class IPInfo(BaseModel):
    name: str = ""
    concept: str = ""
    positioning: str = ""
    selling_point: str = ""
    target_audience: str = ""
    emotional_value: str = ""
    visual_style: str = ""


class WorldInfo(BaseModel):
    time_setting: str = ""
    world_rules: str = ""
    event_cause: str = ""
    core_conflict: str = ""
    player_identity: str = ""
    player_goal: str = ""
    final_goal: str = ""
    culture_relation: str = ""


class Character(BaseModel):
    character_id: str
    name: str
    role: str
    personality: str = ""
    background: str = ""
    function: str = ""
    appearance: str = ""
    appearance_mode: Literal["online", "offline", "both"] = "both"


class StoryInfo(BaseModel):
    synopsis: str = ""
    background: str = ""
    event: str = ""
    player_intervention: str = ""
    player_goal: str = ""
    conflict_escalation: str = ""
    info_reveal: str = ""
    climax: str = ""
    ending: str = ""


class CultureResource(BaseModel):
    resource_id: str
    name: str = ""
    description: str = ""
    authenticity: Literal["REAL", "ADAPTED", "FICTIONAL"] = "REAL"
    source: str = ""
    plot_role: str = ""
    task_role: str = ""
    spatial_node: str = ""
    player_experience: str = ""


class Space(BaseModel):
    space_id: str
    name: str
    type: str = ""
    description: str = ""
    map_position: dict = Field(default_factory=lambda: {"x": 0, "y": 0})


class Task(BaseModel):
    title: str = ""
    objective: str = ""
    player_actions: List[str] = Field(default_factory=list)
    completion_condition: str = ""


class Interaction(BaseModel):
    type: Literal[
        "gps", "ar", "nfc", "physical_device", "npc_dialogue",
        "quiz", "puzzle", "prop", "teamwork", "online"
    ] = "online"
    description: str = ""


class Clue(BaseModel):
    clue_id: str
    name: str = ""
    content: str = ""
    source: str = ""


class Reward(BaseModel):
    type: str = ""
    name: str = ""
    description: str = ""


class PlotNode(BaseModel):
    node_id: str
    sequence: int = 0
    title: str = ""
    space_id: str = ""
    opening_narration: str = ""
    scene: dict = Field(default_factory=lambda: {"description": "", "plot": ""})
    task: Task = Field(default_factory=Task)
    interaction: Interaction = Field(default_factory=Interaction)
    clues: List[Clue] = Field(default_factory=list)
    culture: List[CultureResource] = Field(default_factory=list)
    rewards: List[Reward] = Field(default_factory=list)
    closing_narration: str = ""
    prerequisites: List[str] = Field(default_factory=list)
    next_node_id: str = ""


class NPC(BaseModel):
    npc_id: str
    name: str = ""
    role: str = ""
    personality: str = ""
    background: str = ""
    appearance: str = ""
    appearance_mode: Literal["online", "offline", "both"] = "both"
    function: str = ""
    space_ids: List[str] = Field(default_factory=list)
    plot_node_ids: List[str] = Field(default_factory=list)


class ReviewIssue(BaseModel):
    dimension: str = ""
    severity: str = ""
    description: str = ""
    location: str = ""
    suggestion: str = ""


class Review(BaseModel):
    issues: List[ReviewIssue] = Field(default_factory=list)
    passed: bool = False
    fix_rounds: int = 0


class Script(BaseModel):
    project: Project = Field(default_factory=Project)
    ip: IPInfo = Field(default_factory=IPInfo)
    world: WorldInfo = Field(default_factory=WorldInfo)
    characters: List[Character] = Field(default_factory=list)
    story: StoryInfo = Field(default_factory=StoryInfo)
    culture_resources: List[CultureResource] = Field(default_factory=list)
    spaces: List[Space] = Field(default_factory=list)
    plot_nodes: List[PlotNode] = Field(default_factory=list)
    npcs: List[NPC] = Field(default_factory=list)
    review: Review = Field(default_factory=Review)