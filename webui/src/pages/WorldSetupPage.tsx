import { useParams } from "react-router-dom";

function WorldSetupPage() {
  const { projectId } = useParams();

  return (
    <div>
      <h1 className="text-3xl font-bold">世界记忆初始化</h1>
      <p className="mt-2 text-muted-foreground">
        当前正在编辑的项目 ID: {projectId}
      </p>
    </div>
  );
}

export default WorldSetupPage;
