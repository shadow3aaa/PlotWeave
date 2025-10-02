from typing import Annotated
from langchain_core.tools import tool  # type: ignore
from langgraph.prebuilt import InjectedState
from outline import Outline


@tool
def get_outline_tool(
    outline: Annotated[Outline, InjectedState("outline")],
) -> Outline:
    """
    获取小说大纲
    """
    return outline
