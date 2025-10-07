from enum import Enum
from typing import Annotated, TypedDict
from uuid import UUID
from langchain_core.messages import BaseMessage, AIMessage, ToolMessage, HumanMessage
from langgraph.graph import StateGraph, START, END  # pyright: ignore[reportMissingTypeStubs]
from langchain.chat_models import init_chat_model
from agent_tools import world_tools, writer_tools
from langgraph.prebuilt import ToolNode, InjectedState
from chapter import ChapterInfo
from config import config
from project_metadata import ProjectMetadata
from world import World
from langchain_core.tools import tool, InjectedToolCallId  # type: ignore
import operator
from langgraph.types import Command


class WritingState(str, Enum):
    PLANNING = "计划"
    PROPOSING_CHANGES = "开始提议"
    REVIEW = "审查"
    FINAL_WRITING = "整合写作"
    COMPLETE = "完成"


class State(TypedDict):
    """
    写作agent的状态
    """

    metadata: ProjectMetadata
    """
    当前项目元数据
    """

    messages: Annotated[list[BaseMessage], operator.add]
    """
    会话历史
    """

    project_id: UUID
    """
    当前项目ID
    """

    writing_state: WritingState
    """
    当前写作状态
    """

    current_chapter_index: int
    """
    当前章节索引
    """

    current_chapter_info: ChapterInfo
    """
    当前章节信息
    """

    world: World
    """
    世界记忆图谱
    """

    approved_events: Annotated[list[str], operator.add]
    """
    已批准的事件列表
    """


graph_builder = StateGraph(State)


@tool
def switch_writing_state_tool(
    state: WritingState,
    previous_state: Annotated[WritingState, InjectedState("writing_state")],
    tool_call_id: Annotated[str, InjectedToolCallId],
) -> Command[WritingState]:
    """
    切换写作状态。用于在 '计划', '提议', '整合写作', '完成' 之间切换。
    """
    print(f"请求切换写作状态到 {state}，当前状态是 {previous_state}")
    if state == previous_state:
        return Command()

    match state:
        case WritingState.PROPOSING_CHANGES:
            if previous_state != WritingState.PLANNING:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                tool_call_id=tool_call_id,
                                content=f"无法从当前状态 {previous_state} 切换到 {state}，在提议之前必须先进行计划",
                            )
                        ]
                    }
                )
        case WritingState.FINAL_WRITING:
            if previous_state != WritingState.PLANNING:
                return Command(
                    update={
                        "messages": [
                            ToolMessage(
                                tool_call_id=tool_call_id,
                                content=f"无法从当前状态 {previous_state} 切换到 {state}，必须在所有计划完成后才能进入整合写作阶段",
                            )
                        ]
                    }
                )
        case _:
            pass
    print(f"成功切换写作状态到 {state}")
    return Command(
        update={
            "writing_state": state,
            "messages": [
                ToolMessage(
                    tool_call_id=tool_call_id, content=f"切换写作状态到 {state}"
                )
            ],
        }
    )


llm = init_chat_model(
    model=config.writer_model,
    model_provider="openai",
    base_url=config.writer_base_url,
    api_key=config.writer_api_key,
)
tools = (
    world_tools.read_and_append_tools
    + writer_tools.full_tools
    + [switch_writing_state_tool]
)
llm_with_tools = llm.bind_tools(  # pyright: ignore[reportUnknownMemberType]
    tools=tools
)


def build_hint_prompt(
    state: State,
) -> str:
    """
    构建并返回任务提示语
    """
    writing_state = state["writing_state"]
    chapter_info = state["current_chapter_info"]
    approved_events = state.get("approved_events", [])

    approved_events_str = (
        "\n".join(f"- {event}" for event in approved_events)
        if approved_events
        else "无"
    )

    match writing_state:
        case WritingState.PLANNING:
            return f"""章节标题: {chapter_info.title}
章节意图: {chapter_info.intent}

当前处于小说写作的【计划阶段】。
你的任务是为推进章节意图制定下一步的计划。请遵循“小步快跑”的原则，每次只计划一个微小的推进。
请使用相关工具收集世界图谱当前信息，确保你的计划与当前世界状态衔接。

**已批准的事件列表**:
{approved_events_str}

**下一步行动**:
1.  **继续计划**: 如果章节意图尚未完成，请构思下一步的事件，并使用工具收集信息进行详细规划。规划完成后，使用`switch_writing_state_tool`切换到`开始提议`阶段。
2.  **完成计划**: 如果你认为基于上面的事件列表，章节意图已经可以完整表达，无需再添加新的事件，请调用`switch_writing_state_tool`工具，将状态切换到`整合写作`阶段，以完成本章。
            """
        case WritingState.PROPOSING_CHANGES:
            return f"""章节标题: {chapter_info.title}
章节意图: {chapter_info.intent}

当前处于小说写作的【提议阶段】。
你已经有了计划，现在请提出具体的、可执行的世界记忆图谱修改建议以推进该计划。
注意你提出的修改应该尽量详细且具体，严格按照计划进行，不要进行与计划无关的修改。

在你认为提议完成之后，调用 `switch_writing_state_tool` 工具，将状态切换到 `审查` 阶段。
"""
        case WritingState.REVIEW:
            raise ValueError("REVIEW阶段不应该出现在llm节点")
        case WritingState.FINAL_WRITING:
            return f"""章节标题: {chapter_info.title}
章节意图: {chapter_info.intent}

当前处于小说写作的【整合写作阶段】。
本章的所有计划和世界状态变更均已完成。

本章发生的世界状态变更:
{approved_events_str}

你的任务:
作为一名优秀的小说家，请将上述所有事件串联起来，创作一篇情节连贯、文笔流畅、内容完整的章节。
不要出现任何与世界状态变更无关的内容，也不要写成日记或流水账的形式，以优雅的叙述方式和文笔展现世界状态的变更。
请使用 `add_paragraph_tool` 工具，**可以多次调用**，分段落输出最终的章节内容。
在完成整章的写作后，调用 `switch_writing_state_tool` 将状态切换到 `完成` 阶段。
            """
        case WritingState.COMPLETE:
            raise ValueError("COMPLETE阶段不应该出现在llm节点")


def writer_bot(state: State):
    """
    llm节点
    """
    injected_hint = build_hint_prompt(state)
    injected_message = HumanMessage(
        content=f"--- 当前模式的提示 ---\n\n{injected_hint}\n\n--- 当前模式的提示 ---"
    )

    messages = [*state["messages"], injected_message]
    return {"messages": [injected_message, llm_with_tools.invoke(messages)]}


def review_node(
    state: State,
):
    """
    监督节点
    """
    # TODO: 实现更复杂的监督逻辑

    proposal_summary = "一项修改已通过审查。"
    for msg in reversed(state["messages"]):
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", []):
            tool_names = [tc["name"] for tc in msg.tool_calls]
            is_world_modification = any(
                tool_name
                in [
                    "add_entity_tool",
                    "update_entity_property_tool",
                    "add_relation_tool",
                ]
                for tool_name in tool_names
            )

            if is_world_modification and msg.content:  # pyright: ignore[reportUnknownMemberType]
                if isinstance(msg.content, str):  # pyright: ignore[reportUnknownMemberType]
                    proposal_summary = msg.content
                else:
                    raise ValueError("AIMessage content is not str")
                break

    feedback_message = HumanMessage(
        content=f"系统审查通过了你的提议。事件“{proposal_summary}”已记录。现在请继续为推进章节意图进行下一步的计划。"
    )

    return {
        "writing_state": WritingState.PLANNING,
        "approved_events": [proposal_summary],
        "messages": [feedback_message],
    }


# MODIFIED: 这是本次修复的核心，重写了路由函数
def router_edge(state: State):
    """
    路由边，决定下一个要执行的节点。
    """
    messages = state["messages"]
    last_msg = messages[-1]

    if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", []):
        return "tools"

    match state["writing_state"]:
        case WritingState.COMPLETE:
            state["metadata"].writing_chapter_index += 1
            return END
        case WritingState.REVIEW:
            return "review"
        case _:
            return "writer_bot"


graph_builder.add_node("writer_bot", writer_bot)  # pyright: ignore[reportUnknownMemberType]
graph_builder.add_edge(START, "writer_bot")
tool_node = ToolNode(tools=tools)
graph_builder.add_node("tools", tool_node)  # pyright: ignore[reportUnknownMemberType]
graph_builder.add_node("review", review_node)  # pyright: ignore[reportUnknownMemberType]
graph_builder.add_conditional_edges(
    "writer_bot",
    router_edge,
    # The following dictionary lets you tell the graph to interpret the condition's outputs as a specific node
    # It defaults to the identity function, but if you
    # want to use a node named something else apart from "tools",
    # You can update the value of the dictionary to something else
    # e.g., "tools": "my_tools"
    {"writer_bot": "writer_bot", "tools": "tools", "review": "review", END: END},
)
graph_builder.add_conditional_edges(
    "tools",
    router_edge,
    # The following dictionary lets you tell the graph to interpret the condition's outputs as a specific node
    # It defaults to the identity function, but if you
    # want to use a node named something else apart from "tools",
    # You can update the value of the dictionary to something else
    # e.g., "tools": "my_tools"
    {"writer_bot": "writer_bot", "tools": "tools", "review": "review", END: END},
)
graph_builder.add_edge("review", "writer_bot")


graph = graph_builder.compile()  # pyright: ignore[reportUnknownMemberType]
