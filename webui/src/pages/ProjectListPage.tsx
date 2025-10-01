import { useState, useEffect } from "react";
import {
  ProjectCard,
  ProjectPhase,
  type ProjectMetadata,
} from "@/components/ProjectCard";
import { Button } from "../components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useNavigate } from "react-router-dom";

function ProjectListPage() {
  const [projects, setProjects] = useState<ProjectMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [newProjectName, setNewProjectName] = useState("");
  const [isCreateDialogOpen, setIsCreateDialogOpen] = useState(false);
  const navigate = useNavigate();

  const fetchProjects = async () => {
    try {
      const response = await fetch("/api/projects");
      const data = await response.json();
      setProjects(data.projects);
    } catch (error) {
      console.error("获取项目列表失败:", error);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchProjects();
  }, []);

  const handleCreateProject = async () => {
    if (!newProjectName.trim()) {
      alert("项目名称不能为空");
      return;
    }
    try {
      const response = await fetch("/api/projects", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ name: newProjectName }),
      });
      const newProject: ProjectMetadata = await response.json();

      setProjects((currentProjects) => [newProject, ...currentProjects]);

      setNewProjectName("");
      setIsCreateDialogOpen(false);
    } catch (error) {
      console.error("创建项目失败:", error);
    }
  };

  const handleDeleteProject = async (project: ProjectMetadata) => {
    try {
      const projectId = project.id;
      await fetch(`/api/projects/${projectId}`, {
        method: "DELETE",
      });
      setProjects((currentProjects) =>
        currentProjects.filter((p) => p.id !== projectId),
      );
    } catch (error) {
      console.error("删除项目失败:", error);
    }
  };

  const handleEnterProject = (project: ProjectMetadata) => {
    const { id, phase } = project;
    switch (phase) {
      case ProjectPhase.OUTLINE:
        navigate(`/projects/${id}/outline`);
        break;
      case ProjectPhase.WORLD_SETUP:
        navigate(`/projects/${id}/world-setup`);
        break;
      case ProjectPhase.CHAPERING:
        navigate(`/projects/${id}/chaptering`);
        break;
      case ProjectPhase.CHAPER_WRITING:
        navigate(`/projects/${id}/chapter-writing`);
        break;
      default:
        // 如果没有匹配的 phase，可以导航到一个默认页面，比如大纲页
        navigate(`/projects/${id}`);
        break;
    }
  };

  if (isLoading) {
    return <div className="p-8">正在加载项目...</div>;
  }

  return (
    <div className="container mx-auto p-4 sm:p-8">
      <header className="mb-8 flex justify-between items-center">
        <div>
          <h1 className="text-4xl font-bold">剧情织机</h1>
          <p className="text-muted-foreground">
            选择一个项目开始，或创建一个新项目。
          </p>
        </div>

        <Dialog open={isCreateDialogOpen} onOpenChange={setIsCreateDialogOpen}>
          <DialogTrigger asChild>
            <Button>创建新项目</Button>
          </DialogTrigger>
          <DialogContent className="sm:max-w-[425px]">
            <DialogHeader>
              <DialogTitle>创建新项目</DialogTitle>
              <DialogDescription>
                为您的新故事世界起一个名字。
              </DialogDescription>
            </DialogHeader>
            <div className="grid gap-4 py-4">
              <div className="grid grid-cols-4 items-center gap-4">
                <Label htmlFor="name" className="text-right">
                  名称
                </Label>
                <Input
                  id="name"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="col-span-3"
                  placeholder="例如：我的第一部奇幻小说"
                />
              </div>
            </div>
            <DialogFooter>
              <Button type="submit" onClick={handleCreateProject}>
                创建
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </header>

      <main>
        {projects.length > 0 ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project) => (
              <ProjectCard
                key={project.id}
                project={project}
                onDelete={handleDeleteProject}
                onEnter={handleEnterProject}
              />
            ))}
          </div>
        ) : (
          <div className="text-center py-16">
            <p>还没有项目</p>
          </div>
        )}
      </main>
    </div>
  );
}

export default ProjectListPage;
