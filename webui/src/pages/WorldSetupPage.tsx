import { useState, useRef, type FormEvent, useEffect, useMemo } from "react";
import { useParams, useNavigate } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { Send, ClipboardCopy, Check, Workflow, ArrowRight } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  Accordion,
  AccordionContent,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { cn, streamAsyncIterator } from "@/lib/utils";
import { type ProjectMetadata, ProjectPhase } from "@/components/ProjectCard";
import type { GroupedMessage, Message } from "@/lib/types";

// 用于复制文本的 Hook
const useCopyToClipboard = () => {
  const [isCopied, setIsCopied] = useState(false);
  const copy = (text: string) => {
    navigator.clipboard.writeText(text);
    setIsCopied(true);
    setTimeout(() => setIsCopied(false), 2000);
  };
  return { isCopied, copy };
};

// 单条工具日志组件
const ToolLogEntry = ({ message }: { message: Message }) => {
  const { isCopied, copy } = useCopyToClipboard();
  const title = message.type === "thinking" ? "Agent 思考" : "工具结果";

  return (
    <div className="relative group/log">
      <p className="text-xs font-semibold text-muted-foreground mb-1">
        {title}
      </p>
      <pre className="text-xs whitespace-pre-wrap font-mono bg-muted p-3 rounded-md">
        <code>{message.content}</code>
      </pre>
      <Button
        variant="ghost"
        size="icon"
        className="absolute top-0 right-0 h-6 w-6 opacity-0 group-hover/log:opacity-100 transition-opacity"
        onClick={() => copy(message.content)}
      >
        {isCopied ? (
          <Check className="size-3 text-green-500" />
        ) : (
          <ClipboardCopy className="size-3" />
        )}
      </Button>
    </div>
  );
};

// 工具调用组组件
const ToolGroupMessage = ({ messages }: { messages: Message[] }) => {
  return (
    <div className="flex items-start gap-3">
      <div className="bg-muted rounded-full size-8 flex-shrink-0 flex items-center justify-center">
        <Workflow className="size-5 text-muted-foreground" />
      </div>
      <div className="w-full max-w-[80%]">
        <Accordion type="single" collapsible className="w-full">
          <AccordionItem
            value="item-1"
            className="border rounded-lg bg-background shadow-sm px-3"
          >
            <AccordionTrigger className="py-2 text-sm text-muted-foreground hover:no-underline font-semibold">
              Agent 思考中 ({messages.length} 步)
            </AccordionTrigger>
            <AccordionContent className="border-t pt-3 space-y-3">
              {messages.map((msg) => (
                <ToolLogEntry key={msg.id} message={msg} />
              ))}
            </AccordionContent>
          </AccordionItem>
        </Accordion>
      </div>
    </div>
  );
};

function WorldSetupPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const [project, setProject] = useState<ProjectMetadata | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    const fetchProjectData = async () => {
      if (!projectId) return;
      try {
        const response = await fetch(`/api/projects/${projectId}`);
        if (!response.ok) {
          throw new Error(`获取项目信息失败: ${response.statusText}`);
        }
        const projectData: ProjectMetadata = await response.json();
        setProject(projectData);
      } catch (e) {
        if (e instanceof Error) setError(e.message);
      }
    };
    fetchProjectData();
  }, [projectId]);

  // 使用 useMemo 对消息进行分组，避免每次渲染都重新计算
  const groupedMessages = useMemo(() => {
    const groups: GroupedMessage[] = [];
    let currentToolGroup: Message[] = [];

    for (const message of messages) {
      const isToolMessage =
        message.type === "thinking" || message.type === "tool_result";

      if (isToolMessage) {
        currentToolGroup.push(message);
      } else {
        if (currentToolGroup.length > 0) {
          groups.push({
            type: "tool_group",
            messages: currentToolGroup,
            id: `group-${currentToolGroup[0].id}`,
          });
          currentToolGroup = [];
        }
        groups.push(message);
      }
    }
    // 处理末尾的工具组
    if (currentToolGroup.length > 0) {
      groups.push({
        type: "tool_group",
        messages: currentToolGroup,
        id: `group-${currentToolGroup[0].id}`,
      });
    }

    return groups;
  }, [messages]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isLoading || !projectId) return;

    setIsLoading(true);
    const currentUserMessage = input;
    const historyBeforeSubmit = messages; // 捕获提交前的历史记录

    // 更新UI
    const userMessage: Message = {
      id: `user-${Date.now()}`,
      role: "user",
      content: currentUserMessage,
    };
    const assistantPlaceholder: Message = {
      id: `assistant-${Date.now()}`,
      role: "assistant",
      content: "",
      type: "final",
    };
    setMessages((prev) => [...prev, userMessage, assistantPlaceholder]);
    setInput("");

    try {
      const response = await fetch(`/api/projects/${projectId}/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          message: currentUserMessage,
          history: historyBeforeSubmit,
        }),
      });

      if (!response.ok || !response.body)
        throw new Error(`请求失败: ${response.statusText}`);

      for await (const chunk of streamAsyncIterator(response.body)) {
        if (chunk) {
          try {
            const parsedData = JSON.parse(chunk);
            const assistantMessageId = assistantPlaceholder.id;

            switch (parsedData.type) {
              case "thinking":
              case "tool_result":
                // 将工具消息插入到占位符之前
                setMessages((prev) => {
                  const last = prev[prev.length - 1];
                  const rest = prev.slice(0, -1);
                  const newLog: Message = {
                    id: `log-${Date.now()}-${Math.random()}`,
                    role: "assistant",
                    content: parsedData.data,
                    type: parsedData.type,
                  };
                  return [...rest, newLog, last];
                });
                break;
              case "token":
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: msg.content + parsedData.data }
                      : msg,
                  ),
                );
                break;
              case "end":
                break;
              case "error":
                setMessages((prev) =>
                  prev.map((msg) =>
                    msg.id === assistantMessageId
                      ? { ...msg, content: `**错误:** ${parsedData.data}` }
                      : msg,
                  ),
                );
                break;
            }
          } catch (error) {
            console.error("解析SSE数据块失败:", chunk, error);
          }
        }
      }
    } catch (error) {
      console.error("流式请求失败:", error);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === assistantPlaceholder.id
            ? { ...msg, content: msg.content + `\n\n**连接错误！**` }
            : msg,
        ),
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleAdvancePhase = async () => {
    if (!projectId || !project) {
      alert("项目数据加载中，请稍候。");
      return;
    }

    try {
      const response = await fetch(`/api/projects/${projectId}`, {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          ...project,
          phase: ProjectPhase.CHAPERING,
        }),
      });

      if (!response.ok) {
        throw new Error("推进项目阶段失败");
      }

      navigate(`/projects/${projectId}/chaptering`);
      window.location.reload();
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      }
    }
  };

  if (error) {
    return <div className="p-8 text-red-500">错误: {error}</div>;
  }

  const isReadOnly = project?.phase !== ProjectPhase.WORLD_SETUP;

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">世界设定助手</h1>
          <p className="mt-2 text-muted-foreground">
            {isReadOnly ? "（只读模式）" : "通过对话来构建和查询你的世界记忆。"}
            当前项目 ID: {projectId}
          </p>
        </div>
        {project?.phase === ProjectPhase.WORLD_SETUP && (
          <Button onClick={handleAdvancePhase}>
            <span>完成世界记忆创建</span>
            <ArrowRight className="h-4 w-4" />
          </Button>
        )}
      </div>
      <Card className="flex-1 grid grid-rows-[1fr,auto] min-h-0">
        <CardContent className="overflow-hidden p-4">
          <ScrollArea className="h-full pr-4">
            <div className="space-y-4">
              {groupedMessages.map((item) => {
                if (item.type === "tool_group") {
                  return (
                    <ToolGroupMessage key={item.id} messages={item.messages} />
                  );
                }

                const m = item; // It's a regular message
                return (
                  <div
                    key={m.id}
                    className={cn(
                      "flex items-start gap-3",
                      m.role === "user" ? "justify-end" : "",
                    )}
                  >
                    {m.role === "assistant" && (
                      <div className="bg-muted rounded-full size-8 flex-shrink-0 flex items-center justify-center">
                        🤖
                      </div>
                    )}
                    <div
                      className={cn(
                        "rounded-lg px-4 py-2 max-w-[80%]",
                        m.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted",
                      )}
                    >
                      <div className="prose dark:prose-invert text-sm max-w-none">
                        <ReactMarkdown>{m.content || "..."}</ReactMarkdown>
                      </div>
                    </div>
                    {m.role === "user" && (
                      <div className="bg-blue-500 text-white rounded-full size-8 flex-shrink-0 flex items-center justify-center">
                        🙂
                      </div>
                    )}
                  </div>
                );
              })}
              <div ref={messagesEndRef} />
            </div>
          </ScrollArea>
        </CardContent>
        <CardFooter className="p-4 border-t">
          <form
            onSubmit={handleSubmit}
            className="flex w-full items-center space-x-2"
          >
            <Input
              value={input}
              placeholder={
                isReadOnly
                  ? "已进入下一阶段，无法编辑"
                  : "例如：他后来怎么样了？"
              }
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading || isReadOnly}
              autoComplete="off"
            />
            <Button
              type="submit"
              disabled={isLoading || isReadOnly}
              size="icon"
              className="flex-shrink-0"
            >
              <Send className="size-4" />
              <span className="sr-only">发送</span>
            </Button>
          </form>
        </CardFooter>
      </Card>
    </div>
  );
}

export default WorldSetupPage;
