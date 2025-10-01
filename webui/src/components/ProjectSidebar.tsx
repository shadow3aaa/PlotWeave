import { useState, useEffect } from "react";
import { NavLink } from "react-router-dom";
import { Home, BookText, Library, Bot, Settings, Split } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarFooter,
} from "@/components/ui/sidebar";
import { Button } from "./ui/button";
import { type ProjectMetadata, ProjectPhase } from "./ProjectCard";

interface ProjectSidebarProps {
  projectId: string;
}

export function ProjectSidebar({ projectId }: ProjectSidebarProps) {
  const [project, setProject] = useState<ProjectMetadata | null>(null);

  useEffect(() => {
    const fetchProject = async () => {
      try {
        const response = await fetch(`/api/projects/${projectId}`);
        if (response.ok) {
          const data = await response.json();
          setProject(data);
        } else {
          console.error("获取项目详情失败");
        }
      } catch (error) {
        console.error("获取项目详情时出错:", error);
      }
    };

    if (projectId) {
      fetchProject();
    }
  }, [projectId]);

  // 辅助函数，用于判断某个阶段是否应该被禁用
  const isPhaseDisabled = (phase: ProjectPhase) => {
    if (!project) return true; // 如果项目数据还未加载，则禁用
    return project.phase < phase;
  };

  return (
    <Sidebar>
      <SidebarHeader>
        <NavLink to="/projects">
          <Button variant="ghost" className="w-full justify-start gap-2 p-2">
            <Home className="h-4 w-4" />
            <span>所有项目</span>
          </Button>
        </NavLink>
      </SidebarHeader>

      <SidebarContent className="p-2">
        <SidebarMenu>
          {/* 大纲设计 */}
          <SidebarMenuItem>
            <NavLink
              to={`/projects/${projectId}/outline`}
              // 使用 pointer-events-none 防止在禁用时点击
              className={
                isPhaseDisabled(ProjectPhase.OUTLINE)
                  ? "pointer-events-none"
                  : ""
              }
            >
              {({ isActive }) => (
                <SidebarMenuButton
                  isActive={isActive}
                  disabled={isPhaseDisabled(ProjectPhase.OUTLINE)}
                >
                  <BookText className="h-4 w-4" />
                  <span>大纲设计</span>
                </SidebarMenuButton>
              )}
            </NavLink>
          </SidebarMenuItem>

          {/* 世界设定 */}
          <SidebarMenuItem>
            <NavLink
              to={`/projects/${projectId}/world-setup`}
              className={
                isPhaseDisabled(ProjectPhase.WORLD_SETUP)
                  ? "pointer-events-none"
                  : ""
              }
            >
              {({ isActive }) => (
                <SidebarMenuButton
                  isActive={isActive}
                  disabled={isPhaseDisabled(ProjectPhase.WORLD_SETUP)}
                >
                  <Library className="h-4 w-4" />
                  <span>世界设定</span>
                </SidebarMenuButton>
              )}
            </NavLink>
          </SidebarMenuItem>

          {/* 分章 */}
          <SidebarMenuItem>
            <NavLink
              to={`/projects/${projectId}/chaptering`}
              className={
                isPhaseDisabled(ProjectPhase.CHAPERING)
                  ? "pointer-events-none"
                  : ""
              }
            >
              {({ isActive }) => (
                <SidebarMenuButton
                  isActive={isActive}
                  disabled={isPhaseDisabled(ProjectPhase.CHAPERING)}
                >
                  <Split className="h-4 w-4" />
                  <span>分章</span>
                </SidebarMenuButton>
              )}
            </NavLink>
          </SidebarMenuItem>

          {/* 章节写作 */}
          <SidebarMenuItem>
            <NavLink
              to={`/projects/${projectId}/chapter-writing`}
              className={
                isPhaseDisabled(ProjectPhase.CHAPER_WRITING)
                  ? "pointer-events-none"
                  : ""
              }
            >
              {({ isActive }) => (
                <SidebarMenuButton
                  isActive={isActive}
                  disabled={isPhaseDisabled(ProjectPhase.CHAPERING)}
                >
                  <Bot className="h-4 w-4" />
                  <span>章节写作</span>
                </SidebarMenuButton>
              )}
            </NavLink>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarContent>

      <SidebarFooter>
        <SidebarMenu className="p-2">
          <SidebarMenuItem>
            <SidebarMenuButton>
              <Settings className="h-4 w-4" />
              <span>项目设置</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
        </SidebarMenu>
      </SidebarFooter>
    </Sidebar>
  );
}
