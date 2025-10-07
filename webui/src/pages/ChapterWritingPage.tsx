import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import {
  List,
  BookOpen,
  Sparkles,
  Save,
  Loader2,
  Circle,
  Pencil,
  Workflow,
  BrainCircuit,
  TerminalSquare,
  AlertTriangle,
  Lock, // 引入 Lock 图标
} from "lucide-react";

import { Button } from "../components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  CardDescription,
} from "../components/ui/card";
import { ScrollArea } from "../components/ui/scroll-area";
import { Textarea } from "../components/ui/textarea";
import { type ProjectMetadata, ProjectPhase } from "../components/ProjectCard";
import { streamAsyncIterator } from "../lib/utils";
import type { ChapterInfo } from "@/lib/types";

// 为此页面定义一个更完整的章节类型
interface ChapterWritingInfo {
  title: string;
  intent: string;
  content: string;
  status: "empty" | "draft";
}

// 写作过程中的日志类型
interface WritingLog {
  id: string;
  type: "thinking" | "tool_result" | "error";
  data: string;
}

// 新的日志条目卡片组件
const LogEntryCard = ({ log }: { log: WritingLog }) => {
  let IconComponent;
  let title;
  let cardClasses;
  let iconClasses;

  switch (log.type) {
    case "thinking":
      IconComponent = BrainCircuit;
      title = "思考中...";
      cardClasses =
        "bg-blue-50 border-blue-200 dark:bg-blue-900/30 dark:border-blue-700";
      iconClasses = "text-blue-500";
      break;
    case "tool_result":
      IconComponent = TerminalSquare;
      title = "工具调用结果";
      cardClasses =
        "bg-green-50 border-green-200 dark:bg-green-900/30 dark:border-green-700";
      iconClasses = "text-green-600";
      break;
    case "error":
      IconComponent = AlertTriangle;
      title = "发生错误";
      cardClasses =
        "bg-red-50 border-red-300 dark:bg-red-900/30 dark:border-red-700";
      iconClasses = "text-red-600";
      break;
    default:
      IconComponent = Workflow;
      title = "日志";
      cardClasses = "bg-muted/50";
      iconClasses = "text-muted-foreground";
  }

  return (
    <div className={`p-3 rounded-lg border flex flex-col gap-2 ${cardClasses}`}>
      <div className="flex items-center gap-2">
        <IconComponent className={`size-4 flex-shrink-0 ${iconClasses}`} />
        <p className={`text-xs font-semibold ${iconClasses}`}>{title}</p>
      </div>
      <p className="text-xs font-mono text-foreground/80 whitespace-pre-wrap break-words">
        {log.data}
      </p>
    </div>
  );
};

function ChapterWritingPage() {
  const { projectId } = useParams<{ projectId: string }>();

  const [chapters, setChapters] = useState<ChapterWritingInfo[]>([]);
  const [selectedChapterIndex, setSelectedChapterIndex] = useState<
    number | null
  >(null);
  const [currentWritableIndex, setCurrentWritableIndex] = useState<
    number | null
  >(null); // 新增状态：当前可写作的章节索引
  const [currentContent, setCurrentContent] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [writingLogs, setWritingLogs] = useState<WritingLog[]>([]);
  const [project, setProject] = useState<ProjectMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);
  const logsEndRef = useRef<HTMLDivElement>(null);

  const isReadOnly = project?.phase !== ProjectPhase.CHAPER_WRITING;

  const fetchProjectData = useCallback(async () => {
    if (!projectId) return;
    try {
      const response = await fetch(`/api/projects/${projectId}`);
      if (!response.ok) throw new Error("获取项目信息失败");
      const data = await response.json();
      setProject(data);
    } catch (e) {
      if (e instanceof Error) setError(e.message);
    }
  }, [projectId]);

  // 新增函数：获取当前可写作的章节索引
  const fetchWritableIndex = useCallback(async () => {
    if (!projectId) return;
    try {
      const response = await fetch(
        `/api/projects/${projectId}/write/current_chapter_index`,
      );
      if (!response.ok) throw new Error("获取当前写作章节索引失败");
      const data = await response.json();
      setCurrentWritableIndex(data);
    } catch (e) {
      if (e instanceof Error) setError(e.message);
    }
  }, [projectId]);

  const fetchChapters = useCallback(
    async (selectFirst = false) => {
      if (!projectId) return;
      try {
        const response = await fetch(`/api/projects/${projectId}/chapters`);
        if (!response.ok)
          throw new Error(`获取章节列表失败: ${response.statusText}`);
        const data = await response.json();

        const chapterInfos: ChapterWritingInfo[] = await Promise.all(
          (data.chapters || []).map(
            async (chap: ChapterInfo, index: number) => {
              try {
                const contentRes = await fetch(
                  `/api/projects/${projectId}/chapters/${index}`,
                );
                if (contentRes.ok) {
                  const contentText = await contentRes.text();
                  return {
                    title: chap.title,
                    intent: chap.intent,
                    content: contentText,
                    status: contentText ? "draft" : "empty",
                  };
                }
                return {
                  title: chap.title,
                  intent: chap.intent,
                  content: "",
                  status: "empty",
                };
              } catch (error) {
                console.error(`获取章节 ${index} 内容失败:`, error);
                return {
                  title: chap.title,
                  intent: chap.intent,
                  content: "",
                  status: "empty",
                };
              }
            },
          ),
        );

        setChapters(chapterInfos);

        if (selectFirst && chapterInfos.length > 0) {
          // 默认选中第一个或当前可写的章节
          setSelectedChapterIndex(currentWritableIndex ?? 0);
        }
      } catch (e) {
        if (e instanceof Error) setError(e.message);
      }
    },
    [projectId, currentWritableIndex],
  );

  useEffect(() => {
    fetchProjectData();
    fetchWritableIndex(); // 同时获取可写章节索引
    fetchChapters(true);
  }, [fetchProjectData, fetchChapters, fetchWritableIndex]);

  useEffect(() => {
    const selected =
      selectedChapterIndex !== null ? chapters[selectedChapterIndex] : null;
    setCurrentContent(selected?.content || "");
  }, [selectedChapterIndex, chapters]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [writingLogs]); // 依赖项是 writingLogs，每次日志更新时触发

  const getStatusIcon = (
    status: ChapterWritingInfo["status"],
    index: number,
  ) => {
    // 判断章节是否被锁定
    const isLocked =
      currentWritableIndex !== null && index > currentWritableIndex;

    if (isLocked) {
      return <Lock className="size-4 text-muted-foreground flex-shrink-0" />;
    }

    switch (status) {
      case "draft":
        return <Pencil className="size-4 text-yellow-500 flex-shrink-0" />;
      case "empty":
      default:
        return (
          <Circle className="size-4 text-muted-foreground flex-shrink-0" />
        );
    }
  };

  const handleGenerate = async () => {
    if (
      selectedChapterIndex === null ||
      !projectId ||
      !chapters[selectedChapterIndex]
    )
      return;

    setIsGenerating(true);
    setCurrentContent("");
    setWritingLogs([]);
    setError(null);

    try {
      const chapter_info = {
        title: chapters[selectedChapterIndex].title,
        intent: chapters[selectedChapterIndex].intent,
      };

      const startResponse = await fetch(
        `/api/projects/${projectId}/write/start`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            chapter_index: selectedChapterIndex,
            chapter_info,
          }),
        },
      );

      if (startResponse.status !== 202) {
        const errorData = await startResponse.json();
        throw new Error(
          `启动写作任务失败: ${errorData.detail || "Unknown error"}`,
        );
      }

      const progressResponse = await fetch(
        `/api/projects/${projectId}/write/stream`,
      );
      if (!progressResponse.ok || !progressResponse.body) {
        throw new Error("连接到进度流失败");
      }

      for await (const chunk of streamAsyncIterator(progressResponse.body)) {
        if (chunk) {
          try {
            const event = JSON.parse(chunk);
            switch (event.type) {
              case "content_chunk":
                setCurrentContent((prev) => prev + event.data);
                break;
              case "thinking":
              case "tool_result":
              case "error":
                setWritingLogs((prev) => [
                  ...prev,
                  { id: `log-${Date.now()}-${Math.random()}`, ...event },
                ]);
                break;
              case "end":
                console.log("写作任务流结束");
                break;
            }
          } catch (e) {
            console.error("SSE 解析错误:", e);
          }
        }
      }
    } catch (err) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setIsGenerating(false);
      await fetchChapters(); // 重新获取章节状态
      await fetchWritableIndex(); // 重新获取可写索引，可能会解锁下一章
    }
  };

  const handleSave = async () => {
    if (selectedChapterIndex === null || !projectId || isSaving) return;
    setIsSaving(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/projects/${projectId}/chapters/${selectedChapterIndex}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content: currentContent }),
        },
      );
      if (!response.ok) throw new Error(`保存失败: ${response.statusText}`);

      setChapters((prev) =>
        prev.map((chap, index) =>
          index === selectedChapterIndex
            ? {
                ...chap,
                content: currentContent,
                status: currentContent ? "draft" : "empty",
              }
            : chap,
        ),
      );
    } catch (err) {
      if (err instanceof Error) setError(err.message);
    } finally {
      setIsSaving(false);
      // 保存草稿不一定解锁下一章，但可以同步一下状态
      await fetchWritableIndex();
    }
  };

  const selectedChapter =
    selectedChapterIndex !== null ? chapters[selectedChapterIndex] : null;
  // 判断当前选中的章节是否被锁定
  const isCurrentChapterLocked =
    selectedChapterIndex !== null &&
    currentWritableIndex !== null &&
    selectedChapterIndex > currentWritableIndex;

  return (
    <div className="flex flex-col h-full gap-4">
      <div>
        <h1 className="text-3xl font-bold">章节写作</h1>
        <p className="mt-2 text-muted-foreground">
          {isReadOnly ? "（只读模式）" : "将你的创意转化为生动的文字。"}
        </p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8 flex-1 min-h-0">
        <Card className="lg:col-span-1 flex flex-col min-h-0">
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <List className="size-5" /> 章节导航
            </CardTitle>
          </CardHeader>
          <CardContent className="flex-1 overflow-hidden p-2">
            <ScrollArea className="h-full">
              <div className="space-y-2 pr-2">
                {chapters.map((chap, index) => {
                  const isLocked =
                    currentWritableIndex !== null &&
                    index > currentWritableIndex;
                  return (
                    <Button
                      key={index}
                      variant={
                        selectedChapterIndex === index ? "secondary" : "ghost"
                      }
                      className="w-full justify-start h-auto text-left"
                      onClick={() => setSelectedChapterIndex(index)}
                      disabled={isLocked} // 禁用锁定的章节
                      title={isLocked ? "请先完成前面的章节" : ""}
                    >
                      <div className="flex items-start gap-3 p-1">
                        {getStatusIcon(chap.status, index)}
                        <div>
                          <p className="font-semibold">{chap.title}</p>
                          <p className="text-xs text-muted-foreground font-normal whitespace-normal">
                            {chap.intent}
                          </p>
                        </div>
                      </div>
                    </Button>
                  );
                })}
              </div>
            </ScrollArea>
          </CardContent>
        </Card>

        <Card className="lg:col-span-2 flex flex-col min-h-0">
          {selectedChapter ? (
            <>
              <CardHeader>
                <CardTitle>{selectedChapter.title}</CardTitle>
                <CardDescription>{selectedChapter.intent}</CardDescription>
                <div className="flex items-center gap-2 pt-2">
                  <Button
                    onClick={handleGenerate}
                    disabled={
                      isGenerating ||
                      isSaving ||
                      isReadOnly ||
                      selectedChapterIndex !== currentWritableIndex // 只能生成当前可写的章节
                    }
                  >
                    {isGenerating ? (
                      <Loader2 className="size-4 mr-2 animate-spin" />
                    ) : (
                      <Sparkles className="size-4 mr-2" />
                    )}
                    {isGenerating
                      ? "生成中..."
                      : selectedChapter.status !== "empty"
                        ? "重新生成"
                        : "生成内容"}
                  </Button>
                  <Button
                    onClick={handleSave}
                    variant="outline"
                    disabled={
                      isGenerating ||
                      isSaving ||
                      isReadOnly ||
                      isCurrentChapterLocked // 不能保存未解锁的章节
                    }
                  >
                    {isSaving ? (
                      <Loader2 className="size-4 mr-2 animate-spin" />
                    ) : (
                      <Save className="size-4 mr-2" />
                    )}
                    保存
                  </Button>
                </div>
              </CardHeader>

              <CardContent className="flex-1 flex flex-col gap-4 overflow-hidden p-4">
                {/* 文本编辑区 */}
                <div className="flex-1 flex flex-col min-h-0">
                  <ScrollArea className="h-full w-full rounded-md border">
                    <Textarea
                      className="flex-1 resize-none w-full h-full p-4 border-0 focus-visible:ring-0"
                      value={currentContent}
                      onChange={(e) => setCurrentContent(e.target.value)}
                      placeholder={
                        isGenerating
                          ? "写作 Agent 正在奋笔疾书..."
                          : "点击“生成内容”开始创作，或在此处手动输入..."
                      }
                      disabled={
                        isGenerating || isReadOnly || isCurrentChapterLocked // 不能编辑未解锁的章节
                      }
                    />
                  </ScrollArea>
                </div>
                {/* Agent 日志区 */}
                <p className="text-sm font-semibold pb-2 flex items-center gap-2">
                  <Workflow className="size-4" /> Agent 工作日志
                </p>
                <div className="flex-1 flex flex-col min-h-0">
                  <ScrollArea className="h-full flex-1 bg-muted/50 rounded-md p-4">
                    {writingLogs.length > 0 ? (
                      <div className="space-y-3">
                        {writingLogs.map((log) => (
                          <LogEntryCard key={log.id} log={log} />
                        ))}
                        <div ref={logsEndRef} />
                      </div>
                    ) : (
                      <div className="text-center text-muted-foreground text-sm py-4 h-full flex items-center justify-center">
                        {isGenerating
                          ? "等待 Agent 日志..."
                          : "此处将显示写作过程中的 Agent 思考和工具调用日志。"}
                      </div>
                    )}
                  </ScrollArea>
                </div>
              </CardContent>
            </>
          ) : (
            <div className="flex flex-col items-center justify-center h-full text-muted-foreground">
              <BookOpen className="size-12 mb-4" />
              <p>
                {chapters.length > 0
                  ? "请从左侧选择一个章节开始写作"
                  : "请先在“分章”阶段创建章节"}
              </p>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}

export default ChapterWritingPage;
