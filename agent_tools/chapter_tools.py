from typing import Annotated
from langchain_core.tools import tool, BaseTool  # type: ignore
from langgraph.prebuilt import InjectedState
from openai import BaseModel
from pydantic import Field
from agent_tools.outline_tools import get_outline_tool
from chapter import ChapterInfo, ChapterInfos


class StrippedChapterInfo(BaseModel):
    """
    精简的章节信息，只包含标题
    """

    title: str = Field(description="章节标题")


@tool
def get_chapter_infos_tool(
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
) -> list[str] | str:
    """
    获取章节信息

    注意，这里只返回章节标题的精简版本，如果需要包括意图在内的更多信息，请使用 get_chapter_info_by_index_tool 或 get_chapter_info_by_title_tool
    """
    if len(chapter_infos.chapters) == 0:
        return "当前没有章节信息"
    else:
        return [ci.title for ci in chapter_infos.chapters]


@tool
def get_chapter_info_tool(
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
    title: str,
) -> ChapterInfo | str:
    """
    根据章节标题获取章节信息
    """
    for ci in chapter_infos.chapters:
        if ci.title == title:
            return ci
    return "未找到指定标题的章节信息"


@tool
def delete_chapter_by_title_tool(
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
    title: str,
) -> str:
    """
    根据章节标题删除章节信息
    """
    for i, ci in enumerate(chapter_infos.chapters):
        if ci.title == title:
            del chapter_infos.chapters[i]
            return f"已删除章节: {title}"
    return "未找到指定标题的章节信息"


@tool
def delete_chapter_by_index_tool(
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
    index: int,
) -> str:
    """
    根据章节索引删除章节信息

    注意索引从 0 开始，合法索引范围为 0 到 总章节数 - 1
    """
    if 0 <= index < len(chapter_infos.chapters):
        deleted_title = chapter_infos.chapters[index].title
        del chapter_infos.chapters[index]
        return f"已删除章节: {deleted_title}"
    else:
        return "索引超出范围"


@tool
def add_chapter_tool_to_end_tool(
    title: str,
    intent: str,
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
) -> str:
    """
    添加新的章节为最新章节
    """

    # 检查标题是否已存在
    for ci in chapter_infos.chapters:
        if ci.title == title:
            return "章节标题已存在，请使用不同的标题。"

    chapter_infos.chapters.append(ChapterInfo(title=title, intent=intent))
    return f"已添加章节: {title}"


@tool
def add_chapter_tool_after_tool(
    title: str,
    intent: str,
    after_title: str,
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
) -> str:
    """
    添加新的章节在指定标题章节之后
    """

    # 检查标题是否已存在
    for ci in chapter_infos.chapters:
        if ci.title == title:
            return "章节标题已存在，请使用不同的标题。"

    for i, ci in enumerate(chapter_infos.chapters):
        if ci.title == after_title:
            chapter_infos.chapters.insert(
                i + 1, ChapterInfo(title=title, intent=intent)
            )
            return f"已添加章节: {title} 在 {after_title} 之后"
    return "未找到指定标题的章节信息"


@tool
def add_chapter_tool_before_tool(
    title: str,
    intent: str,
    before_title: str,
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
) -> str:
    """
    添加新的章节在指定标题章节之前
    """

    # 检查标题是否已存在
    for ci in chapter_infos.chapters:
        if ci.title == title:
            return "章节标题已存在，请使用不同的标题。"

    for i, ci in enumerate(chapter_infos.chapters):
        if ci.title == before_title:
            chapter_infos.chapters.insert(i, ChapterInfo(title=title, intent=intent))
            return f"已添加章节: {title} 在 {before_title} 之前"
    return "未找到指定标题的章节信息"


@tool
def replace_chapter_intent_tool(
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
    title: str,
    new_intent: str,
) -> str:
    """
    替换章节意图
    """
    for ci in chapter_infos.chapters:
        if ci.title == title:
            ci.intent = new_intent
            return f"已更新章节 '{title}' 的意图。"
    return "未找到指定标题的章节信息"


@tool
def replace_chapter_title_tool(
    chapter_infos: Annotated[ChapterInfos, InjectedState("chapter_infos")],
    old_title: str,
    new_title: str,
) -> str:
    """
    替换章节标题
    """
    for ci in chapter_infos.chapters:
        if ci.title == old_title:
            ci.title = new_title
            return f"已更新章节标题从 '{old_title}' 到 '{new_title}'。"
    return "未找到指定标题的章节信息"


full_tools: list[BaseTool] = [
    get_outline_tool,
    get_chapter_infos_tool,
    get_chapter_info_tool,
    delete_chapter_by_title_tool,
    delete_chapter_by_index_tool,
    add_chapter_tool_to_end_tool,
    add_chapter_tool_after_tool,
    add_chapter_tool_before_tool,
    replace_chapter_intent_tool,
    replace_chapter_title_tool,
]
