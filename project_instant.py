from uuid import UUID, uuid4

from chapter import ChapterInfo, ChapterInfos
import chapter
from outline import Outline
import outline
from project_metadata import ProjectMetadata, ProjectPhase
import project_metadata
from world import World


class ProjectInstant:
    """
    持有一个小说项目的所有数据

    目前包括

    - 项目名
    - 世界记忆
    - 大纲
    - 分章
    - 小说实际文字内容

    可从文件系统加载和保存
    """

    def __init__(self, name: str):
        """
        初始化一个小说项目

        注意这不是从文件系统加载已有的

        - name: 项目名，可与已有的重复
        """

        self.id = uuid4()
        self.world = World(persistent_path=instant_directory(self.id))
        self.outline = Outline(title="未命名小说", plots=[])
        self.chapter_infos = ChapterInfos()
        self.metadata = ProjectMetadata(
            name=name, id=str(self.id), phase=ProjectPhase.OUTLINE
        )

    async def initialize(self):
        """
        初始化一些异步资源，必须在创建之后尽早调用
        """
        await self.world.initialize()

    async def close(self):
        """
        关闭并释放项目持有的所有资源，例如数据库连接。
        """
        await self.world.close()


async def load_from_directory(dir: str) -> ProjectInstant:
    """
    从指定目录加载小说项目

    - dir: 小说项目的根目录
    """

    # 绕过__init__创建空白实例
    instant = ProjectInstant.__new__(ProjectInstant)
    instant.id = extract_id_from_directory(dir)
    instant.metadata = await project_metadata.load_from_file(metadata_path(instant.id))
    instant.world = World(persistent_path=dir)
    instant.outline = await outline.load_from_file(outline_path(instant.id))
    instant.chapter_infos = await chapter.load_from_file(chapter_infos_path(instant.id))
    return instant


async def save_to_directory(instant: ProjectInstant):
    """
    将小说项目保存到指定目录

    - instant: 小说项目实例

    不需要指定目录，它由实例的 UUID 自动决定
    """

    await project_metadata.save_to_file(instant.metadata, metadata_path(instant.id))
    await outline.save_to_file(instant.outline, outline_path(instant.id))
    await chapter.save_to_file(instant.chapter_infos, chapter_infos_path(instant.id))
    await instant.world.sync_to_disk()


def extract_id_from_directory(dir: str) -> UUID:
    """
    从指定目录提取小说项目的 UUID

    这里假设目录合法
    """
    parts = dir.split("/")
    if len(parts) == 0:
        raise ValueError(f"无法从目录 '{dir}' 提取 UUID")
    return UUID(parts[-1])


def instant_directory(id: UUID) -> str:
    """
    获取某个小说项目的根存储目录

    - id: 小说项目的 UUID
    """
    return f"datas/{id}"


def metadata_path(id: UUID) -> str:
    """
    获取某个小说项目的元数据文件路径

    - id: 小说项目的 UUID
    """
    return f"{instant_directory(id)}/metadata.json"


def qdrant_path(id: UUID) -> str:
    """
    获取某个小说项目的 Qdrant 数据库文件路径

    - id: 小说项目的 UUID
    """
    return f"{instant_directory(id)}/qdrant"


def outline_path(id: UUID) -> str:
    """
    获取某个小说项目的大纲文件路径

    - id: 小说项目的 UUID
    """
    return f"{instant_directory(id)}/outline.yaml"


def chapter_infos_path(id: UUID) -> str:
    """
    获取某个小说项目的章节信息文件路径

    - id: 小说项目的 UUID
    """
    return f"{instant_directory(id)}/chapter_infos.yaml"


def output_path(id: UUID, chapter_index: int, chapter_info: ChapterInfo) -> str:
    """
    获取某个小说项目指定章节的输出文件路径

    - id: 小说项目的 UUID
    - chapter_info: 章节信息
    """
    return (
        f"{instant_directory(id)}/outputs/{chapter_index:02d}_{chapter_info.title}.md"
    )
