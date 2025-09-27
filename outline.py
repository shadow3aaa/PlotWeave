from pydantic import BaseModel, ValidationError
import yaml
import aiofiles


class Outline(BaseModel):
    """
    小说大纲

    包括以下内容

    - title: 小说标题
    - plots: 主要情节列表
    """

    title: str = "未命名小说"
    plots: list[str] = []


class OutlineLoadError(Exception):
    """加载大纲文件时发生错误的基类"""

    pass


class OutlineSaveError(Exception):
    """保存大纲文件时发生错误的基类"""

    pass


async def load_from_file(path: str) -> Outline:
    """
    从指定路径加载并验证大纲。

    如果失败，则抛出 OutlineLoadError 异常。
    """
    try:
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
            data = yaml.safe_load(content)
            if not isinstance(data, dict):
                raise OutlineLoadError(f"文件 '{path}' 的内容不是有效的字典结构。")

            # Pydantic v2 推荐用 model_validate
            return Outline.model_validate(data)

    except FileNotFoundError as e:
        raise OutlineLoadError(f"找不到大纲文件 '{path}'。") from e
    except yaml.YAMLError as e:
        raise OutlineLoadError(f"大纲文件 '{path}' YAML 格式无效。") from e
    except ValidationError as e:
        raise OutlineLoadError(f"大纲文件 '{path}' 内容不符合规范。") from e


async def save_to_file(outline: Outline, path: str):
    """
    将大纲保存到指定路径，覆盖已有文件。
    如果失败，则抛出 OutlineSaveError 异常。
    """
    try:
        data_to_save = outline.model_dump()
        async with aiofiles.open(path, "w", encoding="utf-8") as f:
            yaml_str = yaml.dump(data_to_save, allow_unicode=True, sort_keys=False)
            await f.write(yaml_str)

    except IOError as e:
        # 捕获所有可能的IO错误 (如权限不足、路径不存在等)
        raise OutlineSaveError(f"无法将大纲写入文件 '{path}'。") from e
