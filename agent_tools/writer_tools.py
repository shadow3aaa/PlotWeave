import asyncio
import os
from typing import Annotated
from uuid import UUID
import aiofiles
from langchain_core.tools import tool, BaseTool  # type: ignore
from langgraph.prebuilt import InjectedState
from chapter import ChapterInfo
import project_instant


async def append_to_output_file(
    paragraph: str, project_id: UUID, chapter_index: int, chapter_info: ChapterInfo
):
    """
    将段落内容追加到输出文件中，如果文件不存在则创建它
    """
    output_path = project_instant.output_path(project_id, chapter_index, chapter_info)

    # 确保目录存在
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    file_exists = os.path.exists(output_path)
    is_empty = True

    if file_exists:
        # 这里用只读方式检查文件是否为空
        async with aiofiles.open(output_path, mode="r", encoding="utf-8") as f:
            content = await f.read()
            is_empty = content.strip() == ""

    # 再以追加模式写入
    async with aiofiles.open(output_path, mode="a", encoding="utf-8") as f:
        if not file_exists or is_empty:
            await f.write(f"# {chapter_info.title}\n")
        await f.write("\n" + paragraph + "\n")


@tool
def add_paragraph_tool(
    content: str,
    project_id: Annotated[UUID, InjectedState("project_id")],
    current_chapter_index: Annotated[int, InjectedState("current_chapter_index")],
    current_chapter_info: Annotated[ChapterInfo, InjectedState("current_chapter_info")],
) -> str:
    """
    向当前章节添加一个段落

    - content: 要添加的段落内容，不要带有任何格式化标记，使用纯文本
    """

    try:
        asyncio.run(
            append_to_output_file(
                content,
                project_id,
                current_chapter_index,
                current_chapter_info,
            )
        )
        return "段落已成功添加到输出文件。"
    except Exception as e:
        return f"添加段落时出错: {e}"


full_tools: list[BaseTool] = [
    add_paragraph_tool,
]
"""
写作工具列表
"""
