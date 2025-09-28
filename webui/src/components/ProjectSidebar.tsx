import { NavLink } from "react-router-dom";
import { Home, BookText, Library, Bot, Settings } from "lucide-react";
import {
  Sidebar,
  SidebarContent,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuItem,
  SidebarMenuButton,
  SidebarFooter,
  SidebarSeparator,
} from "@/components/ui/sidebar";
import { Button } from "./ui/button";

interface ProjectSidebarProps {
  projectId: string;
}

export function ProjectSidebar({ projectId }: ProjectSidebarProps) {
  return (
    <Sidebar>
      <SidebarHeader>
        {/* 返回项目列表的按钮 */}
        <NavLink to="/projects">
          <Button variant="ghost" className="w-full justify-start gap-2 p-2">
            <Home className="h-4 w-4" />
            <span>所有项目</span>
          </Button>
        </NavLink>
      </SidebarHeader>
      <SidebarSeparator />

      <SidebarContent className="p-2">
        <SidebarMenu>
          {/* 项目级导航链接 */}
          <SidebarMenuItem>
            <NavLink to={`/projects/${projectId}/outline`}>
              {({ isActive }) => (
                <SidebarMenuButton isActive={isActive}>
                  <BookText className="h-4 w-4" />
                  <span>大纲设计</span>
                </SidebarMenuButton>
              )}
            </NavLink>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton disabled>
              <Library className="h-4 w-4" />
              <span>世界设定</span>
            </SidebarMenuButton>
          </SidebarMenuItem>
          <SidebarMenuItem>
            <SidebarMenuButton disabled>
              <Bot className="h-4 w-4" />
              <span>章节写作</span>
            </SidebarMenuButton>
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
