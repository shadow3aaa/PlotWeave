import { useEffect, useState } from "react";
import { ProjectSidebar } from "@/components/ProjectSidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { Outlet, useParams } from "react-router-dom";

function ProjectLayout() {
  const { projectId } = useParams<{ projectId: string }>();
  const [isProjectActive, setIsProjectActive] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    let intervalId: number | undefined;

    const activateAndStartHeartbeat = async () => {
      try {
        // 第一次调用 heartbeat，实际上是激活项目
        const response = await fetch(`/api/projects/${projectId}/heartbeat`, {
          method: "POST",
        });

        if (!response.ok) {
          if (response.status === 404) {
            throw new Error("项目未找到。");
          }
          throw new Error("激活项目失败。");
        }

        console.log(`项目已激活: ${projectId}`);
        setIsProjectActive(true);

        // 项目成功激活后，才开始规律性地发送心跳
        intervalId = setInterval(async () => {
          try {
            await fetch(`/api/projects/${projectId}/heartbeat`, {
              method: "POST",
            });
            console.log(`为项目 ${projectId} 发送了心跳`);
          } catch (error) {
            console.error("后续心跳发送失败:", error);
            return; // 停止尝试发送心跳
          }
        }, 15000);
      } catch (err) {
        if (err instanceof Error) {
          console.error("激活项目失败:", err);
          setError(err.message);
        }
      }
    };

    activateAndStartHeartbeat();

    // 组件卸载时清理定时器
    return () => {
      if (intervalId) {
        clearInterval(intervalId);
        console.log(`已停止为项目 ${projectId} 发送心跳`);
      }
    };
  }, [projectId]);

  // 根据加载状态渲染不同的内容
  const renderContent = () => {
    if (error) {
      return <div className="p-8 text-red-500">错误: {error}</div>;
    }

    if (!isProjectActive) {
      return <div className="p-8">正在加载项目工作区...</div>;
    }

    return <Outlet />;
  };

  return (
    <SidebarProvider className="h-screen bg-background text-foreground">
      <ProjectSidebar projectId={projectId!} />
      <main className="flex-1 min-w-0 overflow-hidden p-4 sm:p-8">
        {renderContent()}
      </main>
    </SidebarProvider>
  );
}

export default ProjectLayout;
