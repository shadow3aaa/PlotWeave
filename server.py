import asyncio
from pathlib import Path
from typing import AsyncGenerator
from fastapi import FastAPI
from pydantic import BaseModel

from project_metadata import ProjectMetadata
import project_metadata

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "欢迎访问剧情织机 (PlotWeave) 后端"}


class ProjectListResponse(BaseModel):
    projects: list[ProjectMetadata]


async def async_rglob(
    root: str | Path,
    pattern: str = "*",
) -> AsyncGenerator[Path, None]:
    """
    异步递归遍历目录，返回匹配到的文件路径。

    - root: 起始目录
    - pattern: 匹配模式，默认为 "*"（所有文件）
    """
    root = Path(root)

    loop = asyncio.get_running_loop()
    files = await loop.run_in_executor(None, lambda: list(root.rglob(pattern)))

    for file in files:
        yield file


@app.get("/api/projects", response_model=ProjectListResponse)
async def list_all_projects():
    """
    获取所有已创建小说项目的元数据列表
    """
    projects_list: list[ProjectMetadata] = []
    async for file in async_rglob(root="datas", pattern="metadata.json"):
        metadata = await project_metadata.load_from_file(str(file))
        projects_list.append(metadata)
    return ProjectListResponse(projects=projects_list)
