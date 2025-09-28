import asyncio
from datetime import datetime, timedelta, timezone
from pathlib import Path
import shutil
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from contextlib import asynccontextmanager

from outline import Outline
from project_instant import ProjectInstant
import project_instant
from project_metadata import ProjectMetadata
import project_metadata


class ActiveProjectManager:
    """
    一个用于管理内存中多个活动项目实例的管理器。
    采用基于 ID 的心跳机制来决定是否释放实例。
    """

    def __init__(self, inactive_timeout_minutes: int = 10):
        # 缓存结构: { project_id: (项目实例, 最后心跳时间) }
        self._active_projects: dict[str, tuple[ProjectInstant, datetime]] = {}
        # 为每个项目ID创建一个锁，防止并发加载时出现竞争条件
        self._locks: dict[str, asyncio.Lock] = {}
        self.inactive_timeout = timedelta(minutes=inactive_timeout_minutes)

    async def get(self, project_id: str) -> ProjectInstant:
        """
        获取一个项目实例。如果实例不在内存中，则从磁盘加载。
        加载后会设置一个初始心跳，等待前端接管。
        """
        if project_id in self._active_projects:
            return self._active_projects[project_id][0]

        lock = self._locks.setdefault(project_id, asyncio.Lock())
        async with lock:
            if project_id in self._active_projects:
                return self._active_projects[project_id][0]

            print(f"加载项目到活动工作区: {project_id}")
            try:
                instance = await project_instant.load_from_directory(project_id)
                # 加载后，设置初始心跳时间
                self._active_projects[project_id] = (
                    instance,
                    datetime.now(timezone.utc),
                )
                return instance
            except FileNotFoundError:
                raise HTTPException(status_code=404, detail="项目文件未找到，无法加载")
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"加载项目时发生错误: {e}")

    def record_heartbeat(self, project_id: str) -> bool:
        """
        记录指定项目的心跳。如果项目不在内存中，则返回 False。
        """
        if project_id in self._active_projects:
            instance, _ = self._active_projects[project_id]
            self._active_projects[project_id] = (instance, datetime.now(timezone.utc))
            return True
        return False

    async def remove(self, project_id: str):
        """
        从内存中手动移除一个项目。
        """

        if project_id in self._active_projects:
            # 同步到磁盘以防数据丢失
            instance, _ = self._active_projects[project_id]
            await project_instant.save_to_directory(instance)
            del self._active_projects[project_id]
        if project_id in self._locks:
            del self._locks[project_id]

    async def cleanup_task(self):
        """
        一个后台任务，定期清理因心跳超时的不活跃项目。
        """
        while True:
            await asyncio.sleep(30)  # 每30s检查一次
            now = datetime.now(timezone.utc)
            inactive_ids = [
                pid
                for pid, (_, last_heartbeat) in self._active_projects.items()
                if now - last_heartbeat > self.inactive_timeout
            ]
            for pid in inactive_ids:
                print(f"释放不活跃的项目实例 (心跳超时): {pid}")
                await self.remove(pid)
            # 同步现有项目到磁盘，防止数据丢失
            for pid in self._active_projects.keys():
                instance, _ = self._active_projects[pid]
                await project_instant.save_to_directory(instance)


active_projects = ActiveProjectManager()


async def guardian_task():
    """
    一个后台任务，定期检查并卸载不活跃的项目。
    """
    await active_projects.cleanup_task()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    启动时创建守护任务，关闭时取消它。
    """
    task = asyncio.create_task(guardian_task())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(lifespan=lifespan)


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


class CreateProjectRequest(BaseModel):
    """
    创建小说项目的请求体
    """

    name: str


@app.post("/api/projects", response_model=ProjectMetadata)
async def create_project(request: CreateProjectRequest):
    """
    创建一个新的小说项目
    """
    instant = ProjectInstant(request.name)
    await instant.initialize()
    await project_instant.save_to_directory(instant)
    return instant.metadata


@app.delete("/api/projects/{project_id}", status_code=200)
async def delete_project(project_id: str):
    """
    删除指定的小说项目
    """
    project_dir = Path("datas") / str(project_id)  # 转换为 str

    if not project_dir.exists() or not project_dir.is_dir():
        raise HTTPException(status_code=404, detail="项目未找到")

    try:
        await active_projects.remove(project_id)
        await asyncio.to_thread(shutil.rmtree, project_dir)
        return {"ok": True, "message": f"项目 {project_id} 已删除"}
    except Exception as e:
        print(f"删除项目时发生错误: {e}")
        raise HTTPException(status_code=500, detail=f"删除项目时发生错误: {e}")


@app.post("/api/projects/{project_id}/heartbeat", status_code=200)
async def project_heartbeat(project_id: str):
    """
    接收前端对指定项目的心跳信号，以保持其活跃。
    如果项目未加载，此端点将触发加载。
    """
    try:
        # get 方法将处理加载逻辑：如果项目不在内存中，则从磁盘加载。
        # 如果项目文件不存在，它会正确地抛出 404 HTTPException。
        await active_projects.get(project_id)

        # 成功获取实例后，我们知道项目肯定在内存中了，再记录心跳。
        active_projects.record_heartbeat(project_id)

        return {"message": f"Project {project_id} is active and heartbeat is recorded."}
    except HTTPException as e:
        # 重新抛出由 get() 引起的 HTTP 异常 (例如 404 Not Found)
        raise e
    except Exception as e:
        # 捕获其他潜在的加载错误
        raise HTTPException(
            status_code=500, detail=f"An error occurred while activating project: {e}"
        )


@app.get("/api/projects/{project_id}/outline", response_model=Outline)
async def get_project_outline(project_id: str):
    """
    获取指定项目的大纲。
    """
    project_instance = await active_projects.get(project_id)
    return project_instance.outline


@app.post("/api/projects/{project_id}/outline", response_model=Outline)
async def update_project_outline(project_id: str, outline: Outline):
    """
    更新指定项目的大纲。
    """
    project_instance = await active_projects.get(project_id)
    project_instance.outline = outline
    return project_instance.outline
