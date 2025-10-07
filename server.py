import asyncio
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import shutil
from typing import Any
import uuid
import aiofiles
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from contextlib import asynccontextmanager
from fastapi.responses import PlainTextResponse
import agent
from agent import world_setup_graph, chaptering_graph

from chapter import ChapterInfo, ChapterInfos
from fs_utils import async_rglob
from outline import Outline
from project_instant import ProjectInstant
import project_instant
from project_metadata import ProjectMetadata, ProjectPhase
from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    AIMessage,
    ToolMessage,
    SystemMessage,
)
import project_metadata
import writer_agent


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
            await instance.close()
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
    一个异步生成器，根据项目阶段动态选择并流式传输 Agent 的响应。
    """
    project_instance = await active_projects.get(project_id)
    if not project_instance:
        error_data = {"type": "error", "data": "项目未加载或不存在。"}
        yield f"data: {json.dumps(error_data)}\n\n"
        return

    # 根据项目阶段选择 Agent 和构建系统提示 ---
    project_phase = project_instance.metadata.phase
    system_prompt = ""
    graph = None

    if project_phase == ProjectPhase.WORLD_SETUP:
        graph = world_setup_graph
        system_prompt = f"""你负责小说世界的初始化。你的任务是帮助用户通过对话构建初始世界记忆图谱。
记住，你要创建世界记忆的状态应当是初始的状态，而非故事结束时的状态。
你可以调用工具来创建实体（人物、地点等）和它们之间的关系。
当前小说大纲：
标题: {project_instance.outline.title}
情节: {", ".join(project_instance.outline.plots)}
"""
    elif project_phase == ProjectPhase.CHAPERING:
        graph = chaptering_graph
        system_prompt = f"""你是一个专业的小说编辑。你的任务是帮助用户将大纲分解为具体的章节。
你可以调用文件系统工具来创建、删除或修改章节文件。
当前小说大纲：
标题: {project_instance.outline.title}
情节: {", ".join(project_instance.outline.plots)}
"""
    else:
        error_data = {
            "type": "error",
            "data": f"项目当前阶段 {project_phase.name} 不支持交互式Agent。",
        }
        yield f"data: {json.dumps(error_data)}\n\n"
        return

    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    for msg in history:
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            messages.append(HumanMessage(content=content))
        elif role == "assistant" and msg.get("type") == "final":
            messages.append(AIMessage(content=content))

    messages.append(HumanMessage(content=user_message))

    state: agent.State = {
        "messages": messages,
        "world": project_instance.world,
        "chapter_infos": project_instance.chapter_infos,
        "outline": project_instance.outline,
    }

    try:
        # 使用动态选择的 graph 进行响应
        async for event in graph.astream(  # type: ignore
            state, config={"recursion_limit": 1145141919819810}
        ):
            for _, value_update in event.items():
                if "messages" in value_update:
                    new_messages = value_update["messages"]
                    if new_messages:
                        latest_message = new_messages[-1]
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


@app.get("/api/projects/{project_id}/chapters", response_model=ChapterInfos)
async def get_project_chapters(project_id: str):
    """
    获取指定项目的所有章节信息。
    """
    project_instance = await active_projects.get(project_id)
    if not project_instance:
        raise HTTPException(status_code=404, detail="项目未加载")
    return project_instance.chapter_infos


@app.get(
    "/api/projects/{project_id}/chapters/{chapter_index}",
    response_class=PlainTextResponse,
)
async def get_project_chapter_content(project_id: str, chapter_index: int):
    """
    获取指定项目的某个章节内容。
    """
    instance = await active_projects.get(project_id)
    # 确保目录存在
    os.makedirs(
        os.path.dirname(
            project_instant.output_path(
                id=instance.id,
                chapter_index=chapter_index,
                chapter_info=instance.chapter_infos.chapters[chapter_index],
            )
        ),
        exist_ok=True,
    )
    if chapter_index < 0 or chapter_index >= len(instance.chapter_infos.chapters):
        raise HTTPException(status_code=400, detail="章节索引无效")
    chapter_info = instance.chapter_infos.chapters[chapter_index]
    try:
        async with aiofiles.open(
            project_instant.output_path(
                id=instance.id, chapter_index=chapter_index, chapter_info=chapter_info
            ),
            mode="r",
            encoding="utf-8",
        ) as f:
            content = await f.read()
            return PlainTextResponse(content=content)
    except FileNotFoundError:
        # 章节文件不存在，创建一个空文件
        async with aiofiles.open(
            project_instant.output_path(
                id=instance.id, chapter_index=chapter_index, chapter_info=chapter_info
            ),
            mode="w",
            encoding="utf-8",
        ) as f:
            await f.write("")
            return PlainTextResponse(content="")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取章节文件时发生错误: {e}")


class ChapterContent(BaseModel):
    content: str


@app.put("/api/projects/{project_id}/chapters/{chapter_index}")
async def save_project_chapter_content(
    project_id: str, chapter_index: int, chapter_body: ChapterContent
):
    instance = await active_projects.get(project_id)
    if chapter_index < 0 or chapter_index >= len(instance.chapter_infos.chapters):
        raise HTTPException(status_code=400, detail="章节索引无效")
    chapter_info = instance.chapter_infos.chapters[chapter_index]
    try:
        async with aiofiles.open(
            project_instant.output_path(
                id=instance.id, chapter_index=chapter_index, chapter_info=chapter_info
            ),
            mode="w",
            encoding="utf-8",
        ) as f:
            await f.write(chapter_body.content)
            return {"message": "章节内容已保存"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"保存章节文件时发生错误: {e}")


writing_event_queues: dict[str, asyncio.Queue[None]] = {}
writing_tasks: dict[str, asyncio.Task[dict[str, Any] | None]] = {}


@app.post("/api/projects/{project_id}/chat/stream")
async def chat_stream(project_id: str, request: ChatRequest):
    """
    与指定项目的 Agent 进行流式对话。
    """
    return StreamingResponse(
        stream_agent_response(project_id, request.message, request.history),
        media_type="text/event-stream",
    )


class WritingRequest(BaseModel):
    """
    启动写作任务的请求体
    """

    chapter_index: int
    chapter_info: ChapterInfo


async def run_writing_agent_in_background(
    project_id: str, chapter_index: int, chapter_info: ChapterInfo
):
    """
    在后台执行写作 Agent 的 langgraph astream，并将事件放入对应的队列。
    """
    # 获取此任务专用的队列
    queue = writing_event_queues.get(project_id)
    if not queue:
        print(f"错误：项目 {project_id} 的事件队列未找到。")
        return

    try:
        project_instance = await active_projects.get(project_id)

        # 初始化 Agent 状态
        init_message = "你是一个专业的小说作家，正在按照预设的流程创作小说段落。"
        state = writer_agent.State(
            messages=[SystemMessage(content=init_message)],
            project_id=uuid.UUID(project_id),
            writing_state=writer_agent.WritingState.PLANNING,
            current_chapter_index=chapter_index,
            current_chapter_info=chapter_info,
            world=project_instance.world,
            metadata=project_instance.metadata,
            approved_events=[],
        )

        async for event in writer_agent.graph.astream(  # pyright: ignore[reportUnknownMemberType]
            state, config={"recursion_limit": 1145141919810}
        ):
            for _, value_update in event.items():
                if "messages" in value_update:
                    latest_message = value_update["messages"][-1]
                    stream_data = None
                    if isinstance(latest_message, AIMessage):
                        if latest_message.tool_calls:
                            tool_name = latest_message.tool_calls[0]["name"]
                            stream_data = {
                                "type": "thinking",
                                "data": f"正在调用工具: `{tool_name}`...",
                            }
                        elif latest_message.content:  # type: ignore
                            stream_data = {  # type: ignore
                                "type": "content_chunk",
                                "data": latest_message.content,  # type: ignore
                            }
                    elif isinstance(latest_message, ToolMessage):
                        stream_data = {
                            "type": "tool_result",
                            "data": f"工具 `{latest_message.name}` 返回: {latest_message.content}",  # type: ignore
                        }

                    if stream_data:
                        await queue.put(stream_data)  # type: ignore

    except Exception as e:
        error_data = {"type": "error", "data": f"写作 Agent 执行出错: {str(e)}"}
        await queue.put(error_data)  # type: ignore
        raise e
    finally:
        print(f"写作任务流结束: 项目 {project_id}, 章节索引 {chapter_index}")
        # 发送结束信号
        end_data = {"type": "end", "data": "写作任务流结束"}
        await queue.put(end_data)  # type: ignore
        # 放入一个 None 来告诉 stream_writing_progress 停止
        await queue.put(None)


@app.post("/api/projects/{project_id}/write/start", status_code=202)
async def start_writing_chapter(project_id: str, request: WritingRequest):
    """
    为指定项目启动一个章节写作任务。
    """
    # 如果已有任务在运行，则不允许启动新任务
    if project_id in writing_tasks and not writing_tasks[project_id].done():
        raise HTTPException(
            status_code=409, detail="该项目已有一个正在进行的写作任务。"
        )

    # 为这个任务创建一个新的事件队列
    writing_event_queues[project_id] = asyncio.Queue()

    # 在后台创建一个 Task 来运行 Agent
    task = asyncio.create_task(
        run_writing_agent_in_background(
            project_id, request.chapter_index, request.chapter_info
        )
    )
    writing_tasks[project_id] = task

    print(f"接收到项目 {project_id} 的写作请求，目标章节索引: {request.chapter_index}")
    return {"message": "写作任务已成功启动"}


@app.get("/api/projects/{project_id}/write/stream")
async def stream_writing_progress(project_id: str):
    """
    连接并流式传输指定项目写作任务的进度。
    """

    async def event_generator():
        """从队列中获取事件并格式化为 SSE"""
        queue = writing_event_queues.get(project_id)
        if not queue:
            # 如果队列不存在，说明任务可能还未启动或已结束
            error_data = {"type": "error", "data": "未找到写作任务流。请先启动任务。"}
            yield f"data: {json.dumps(error_data)}\n\n"
            return

        try:
            while True:
                # 从队列中等待一个事件
                event = await queue.get()
                if event is None:
                    # None 是结束信号
                    break
                yield f"data: {json.dumps(event)}\n\n"
        except asyncio.CancelledError:
            # 当客户端断开连接时，会触发此异常
            print(f"客户端断开连接，停止为项目 {project_id} 发送事件。")
        finally:
            # 清理资源
            if project_id in writing_tasks:
                del writing_tasks[project_id]
            if project_id in writing_event_queues:
                del writing_event_queues[project_id]

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.get("/api/projects/{project_id}/write/current_chapter_index", response_model=int)
async def get_current_writing_chapter_index(project_id: str):
    """
    获取当前正在写作的章节索引。
    """
    instant = await active_projects.get(project_id)
    return instant.metadata.writing_chapter_index
