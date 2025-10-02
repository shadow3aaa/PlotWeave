import aiofiles
from pydantic import BaseModel, Field
import yaml


class ChapterInfo(BaseModel):
    """
    章节信息（不含正文内容）
    """

    title: str = Field(description="未命名章节标题")
    """
    章节标题
    """

    intent: str = Field(description="未命名章节意图")
    """
    章节意图
    """


class ChapterInfos(BaseModel):
    """
    管理并存储章节信息（不含正文内容）
    """

    chapters: list[ChapterInfo] = Field(default_factory=list[ChapterInfo])


async def load_from_file(file_path: str) -> ChapterInfos:
    """
    从指定的 YAML 文件加载章节信息。
    """
    async with aiofiles.open(file_path, mode="r", encoding="utf-8") as f:
        content = await f.read()
        data = yaml.safe_load(content)
        return ChapterInfos.model_validate(data)


async def save_to_file(chapters: ChapterInfos, file_path: str):
    """
    将章节信息保存到指定的 YAML 文件。
    """
    async with aiofiles.open(file_path, mode="w", encoding="utf-8") as f:
        content = yaml.safe_dump(chapters.model_dump())
        await f.write(content)
