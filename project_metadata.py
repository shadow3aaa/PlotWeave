from enum import IntEnum
import aiofiles
from pydantic import BaseModel, ValidationError
import json


class ProjectPhase(IntEnum):
    """
    小说项目的当前阶段

    - OUTLINE: 大纲设计
    - WORLD_SETUP: 世界记忆创建
    - CHAPERING: 分章
    - CHAPER_WRITING: 章节写作
    """

    OUTLINE = 0
    WORLD_SETUP = 1
    CHAPERING = 2
    CHAPER_WRITING = 3


class ProjectMetadata(BaseModel):
    """
    小说项目的元数据

    包括以下内容

    - name: 项目名称
    - phase: 当前阶段
    - id: 项目唯一标识符
    - writing_chapter_index: 当前正在写作的章节索引，默认为 0，表示第一章
    """

    name: str = "未命名项目"
    phase: ProjectPhase
    id: str
    writing_chapter_index: int = 0


class ProjectMetadataSaveError(Exception):
    """保存项目元数据文件时发生错误的基类"""

    pass


class ProjectMetadataLoadError(Exception):
    """加载项目元数据文件时发生错误的基类"""

    pass


async def load_from_file(path: str) -> ProjectMetadata:
    """
    从指定路径加载并验证项目元数据。
    如果失败，则抛出 ProjectMetadataLoadError 异常。
    """
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
            data = json.loads(content)
            if not isinstance(data, dict):
                raise ProjectMetadataLoadError(
                    f"文件 '{path}' 的内容不是有效的字典结构。"
                )

            return ProjectMetadata.model_validate(data)

    except FileNotFoundError as e:
        raise ProjectMetadataLoadError(f"找不到项目元数据文件 '{path}'。") from e
    except json.JSONDecodeError as e:
        raise ProjectMetadataLoadError(
            f"项目元数据文件 '{path}' JSON 格式无效。"
        ) from e
    except ValidationError as e:
        raise ProjectMetadataLoadError(
            f"项目元数据文件 '{path}' 内容不符合规范。"
        ) from e


async def save_to_file(metadata: ProjectMetadata, path: str):
    """
    将项目元数据保存到指定路径，覆盖已有文件。
    如果失败，则抛出 ProjectMetadataSaveError 异常。
    """
    try:
        data_to_save = metadata.model_dump()
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            json_str = json.dumps(data_to_save, ensure_ascii=False, indent=4)
            await f.write(json_str)

    except IOError as e:
        raise ProjectMetadataSaveError(f"无法保存项目元数据到文件 '{path}'。") from e
