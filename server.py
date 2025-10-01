import asyncio
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import shutil
from typing import AsyncGenerator
import uuid
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
import agent
from agent import graph

from outline import Outline
from project_instant import ProjectInstant
import project_instant
from project_metadata import ProjectMetadata
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
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
                instance = await project_instant.load_from_directory(
                    project_instant.instant_directory(uuid.UUID(project_id))
                )
                await instance.initialize()
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

    async def sync_to_disk(self):
        """
        同步现有项目到磁盘
        """
        # 同步现有项目到磁盘，防止数据丢失
        for pid in self._active_projects.keys():
            instance, _ = self._active_projects[pid]
            await project_instant.save_to_directory(instance)

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
            await self.sync_to_disk()


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


@app.get("/api/projects/{project_id}", response_model=ProjectMetadata)
async def get_project_metadata(project_id: str):
    """
    获取指定项目的元数据
    """
    instant = await active_projects.get(project_id)
    return instant.metadata


@app.put("/api/projects/{project_id}", response_model=ProjectMetadata)
async def update_project_metadata(project_id: str, updated_metadata: ProjectMetadata):
    """
    更新指定项目的元数据
    """
    instant = await active_projects.get(project_id)
    instant.metadata = updated_metadata
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
        print(f"项目心跳时发生错误: {e.detail}")
        raise e
    except Exception as e:
        # 捕获其他潜在的加载错误
        print(f"激活项目时发生错误: {e}")
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


@app.put("/api/projects/{project_id}/outline", response_model=Outline)
async def update_project_outline(project_id: str, outline: Outline):
    """
    更新指定项目的大纲。
    """
    project_instance = await active_projects.get(project_id)
    project_instance.outline = outline
    return project_instance.outline


class ChatRequest(BaseModel):
    """
    聊天请求的请求体
    """

    message: str
    history: list[dict[str, str]] = []


async def stream_agent_response(
    project_id: str, user_message: str, history: list[dict[str, str]]
):
    """
    一个异步生成器，用于流式传输 Agent 的响应。
    """
    project_instance = await active_projects.get(project_id)
    if not project_instance:
        error_data = {"type": "error", "data": "项目未加载或不存在。"}
        yield f"data: {json.dumps(error_data)}\n\n"
        return

    # 从前端发送的 history 构建 LangChain 的消息列表
    messages: list[BaseMessage] = []
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        # 我们只将用户和最终的助手回复添加到历史记录中
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant" and msg.get("type") == "final":
            messages.append(AIMessage(content=content))

    # 添加当前用户的新消息
    messages.append(HumanMessage(content=user_message))

    # 使用包含完整历史的消息列表初始化 Agent 状态
    state: agent.State = {
        "messages": messages,
        "world": project_instance.world,
    }

    try:
        # 进行响应
        async for event in graph.astream(state, config={"recursion_limit": 100}):  # pyright: ignore[reportUnknownMemberType]
            for _, value_update in event.items():
                if "messages" in value_update:
                    new_messages = value_update["messages"]
                    if new_messages:
                        latest_message = new_messages[-1]
                        # (这部分的流式输出逻辑保持不变)
                        if isinstance(latest_message, AIMessage):
                            if latest_message.tool_calls:
                                tool_name = latest_message.tool_calls[0]["name"]
                                stream_data = {
                                    "type": "thinking",
                                    "data": f"正在调用工具: `{tool_name}`...",
                                }
                                yield f"data: {json.dumps(stream_data)}\n\n"
                            elif latest_message.content:  # type: ignore
                                stream_data = {  # type: ignore
                                    "type": "token",
                                    "data": latest_message.content,  # type: ignore
                                }
                                yield f"data: {json.dumps(stream_data)}\n\n"
                        elif isinstance(latest_message, ToolMessage):
                            stream_data = {
                                "type": "tool_result",
                                "data": f"工具 `{latest_message.name}` 返回: {latest_message.content}",  # type: ignore
                            }
                            yield f"data: {json.dumps(stream_data)}\n\n"

    except Exception as e:
        print(f"Agent stream error: {e}")
        error_data = {"type": "error", "data": f"Agent 执行出错: {str(e)}"}
        yield f"data: {json.dumps(error_data)}\n\n"
    finally:
        end_data = {"type": "end", "data": "Stream ended"}
        yield f"data: {json.dumps(end_data)}\n\n"


@app.post("/api/projects/{project_id}/chat/stream")
async def chat_stream(project_id: str, request: ChatRequest):
    """
    与指定项目的 Agent 进行流式对话。
    """
    return StreamingResponse(
        stream_agent_response(project_id, request.message, request.history),
        media_type="text/event-stream",
    )
