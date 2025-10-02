from typing import Annotated, TypedDict
from langchain_core.messages import BaseMessage, AIMessage
from langchain_core.tools import BaseTool  # pyright: ignore[reportUnknownVariableType]
import operator
from langgraph.graph import StateGraph, START, END  # pyright: ignore[reportMissingTypeStubs]
from langgraph.prebuilt import ToolNode

from agent_tools import chapter_tools, world_tools
from chapter import ChapterInfos
from config import config
from langchain.chat_models import init_chat_model


from outline import Outline
from world import World


class State(TypedDict):
    messages: Annotated[list[BaseMessage], operator.add]
    """
    会话历史
    """

    world: World
    """
    世界记忆图谱
    """

    chapter_infos: ChapterInfos
    """
    章节信息
    """

    outline: Outline
    """
    小说大纲
    """


graph_builder = StateGraph(State)

llm = init_chat_model(
    model=config.writer_model,
    model_provider="openai",
    base_url=config.writer_base_url,
    api_key=config.writer_api_key,
)


def route_tools(state: State) -> str:
    """
    如果最后一条消息是 AIMessage 且包含 tool_calls，
    就路由到 'tools' 节点，否则直接结束。
    """
    messages = state["messages"]
    last_msg = messages[-1]

    if isinstance(last_msg, AIMessage) and getattr(last_msg, "tool_calls", []):
        return "tools"
    else:
        return END


def build_graph(
    tools: list[BaseTool],
):
    """
    构建并返回特定的图对象
    """
    graph_builder = StateGraph(State)

    llm_with_tools = llm.bind_tools(tools)  # pyright: ignore[reportUnknownMemberType]

    def chatbot(state: State):
        return {"messages": [llm_with_tools.invoke(state["messages"])]}

    graph_builder.add_node("chatbot", chatbot)  # pyright: ignore[reportUnknownMemberType]
    graph_builder.add_edge(START, "chatbot")
    tool_node = ToolNode(tools=tools)
    graph_builder.add_node("tools", tool_node)  # pyright: ignore[reportUnknownMemberType]
    graph_builder.add_edge("tools", "chatbot")
    graph_builder.add_conditional_edges(
        "chatbot",
        route_tools,
        # The following dictionary lets you tell the graph to interpret the condition's outputs as a specific node
        # It defaults to the identity function, but if you
        # want to use a node named something else apart from "tools",
        # You can update the value of the dictionary to something else
        # e.g., "tools": "my_tools"
        {"tools": "tools", END: END},
    )
    return graph_builder.compile()  # pyright: ignore[reportUnknownMemberType]


world_setup_graph = build_graph(tools=world_tools.full_tools)
"""
世界初始化agent的流程图
"""

chaptering_graph = build_graph(
    tools=world_tools.read_only_tools + chapter_tools.full_tools
)
"""
分章agent的流程图
"""
