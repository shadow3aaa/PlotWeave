import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import {
  Card,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";

export interface ProjectMetadata {
  id: string;
  name: string;
}

interface ProjectCardProps {
  project: ProjectMetadata;
  onDelete: (projectId: string) => void;
  onEnter: (projectId: string) => void;
}

export function ProjectCard({ project, onDelete, onEnter }: ProjectCardProps) {
  const handleDelete = () => {
    onDelete(project.id);
  };
  const handleEnter = () => {
    onEnter(project.id);
  };

  return (
    <Card className="flex flex-col">
      <CardHeader>
        <CardTitle>{project.name}</CardTitle>
        <CardDescription>ID: {project.id}</CardDescription>
      </CardHeader>
      <CardFooter className="flex justify-between items-center">
        <div className="flex gap-2">
          <Button onClick={handleEnter}>进入项目</Button>

          <AlertDialog>
            <AlertDialogTrigger asChild>
              <Button variant="destructive">删除</Button>
            </AlertDialogTrigger>
            <AlertDialogContent>
              <AlertDialogHeader>
                <AlertDialogTitle>确定要删除吗?</AlertDialogTitle>
                <AlertDialogDescription>
                  此操作无法撤销。这将永久删除项目 ‘{project.name}’
                  及其所有相关数据。
                </AlertDialogDescription>
              </AlertDialogHeader>
              <AlertDialogFooter>
                <AlertDialogCancel>取消</AlertDialogCancel>
                <AlertDialogAction onClick={handleDelete}>
                  继续删除
                </AlertDialogAction>
              </AlertDialogFooter>
            </AlertDialogContent>
          </AlertDialog>
        </div>
      </CardFooter>
    </Card>
  );
}
