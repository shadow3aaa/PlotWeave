import { useState, useEffect } from "react";
import { ProjectCard, type ProjectMetadata } from "@/components/ProjectCard";
import { Button } from "./components/ui/button";

function App() {
  const [projects, setProjects] = useState<ProjectMetadata[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
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
    fetchProjects();
  }, []);

  if (isLoading) {
    return <div className="p-8">正在加载项目...</div>;
  }

  return (
    <div className="container mx-auto p-4 sm:p-8">
      <header className="mb-8">
        <h1 className="text-4xl font-bold">剧情织机</h1>
        <p className="text-muted-foreground">
          选择一个项目开始，或创建一个新项目。
        </p>
      </header>

      <main>
        {projects.length > 0 ? (
          <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
            {projects.map((project, index) => (
              <ProjectCard key={index} project={project} />
            ))}
          </div>
        ) : (
          <div className="text-center py-16">
            <p>还没有项目</p>
            <Button className="mt-4">创建新项目</Button>
          </div>
        )}
      </main>
    </div>
  );
}

export default App;
