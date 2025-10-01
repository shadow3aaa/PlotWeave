import { useState, useEffect, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import YAML from "yaml";
import Editor from "@monaco-editor/react";
import { Loader2, Check, AlertCircle, ArrowRight } from "lucide-react";
import { ProjectPhase, type ProjectMetadata } from "@/components/ProjectCard";
import { Button } from "@/components/ui/button";

interface OutlineData {
  title: string;
  plots: string[];
}

// 定义保存状态的类型
type SaveStatus = "idle" | "saving" | "success" | "error";

/**
 * 验证数据是否符合 OutlineData 接口的结构和类型
 * @param data - 需要被验证的数据
 * @returns 如果数据有效则返回 true，否则返回 false
 */
function isValidOutlineData(data: unknown): data is OutlineData {
  // Check if data is a non-null, non-array object
  if (typeof data !== "object" || data === null || Array.isArray(data)) {
    return false;
  }

  // Cast to a record to safely check for properties
  const potentialOutline = data as Record<string, unknown>;

  // Check for the 'title' property and its type
  const hasTitle = typeof potentialOutline.title === "string";

  // Check for the 'plots' property and its type (must be an array)
  const hasPlots = Array.isArray(potentialOutline.plots);

  if (!hasTitle || !hasPlots) {
    return false;
  }

  // If 'plots' is an array, check if all its elements are strings
  return (potentialOutline.plots as unknown[]).every(
    (plot: unknown) => typeof plot === "string",
  );
}

function OutlinePage() {
  const { projectId } = useParams<{ projectId: string }>();
  const navigate = useNavigate();

  const [outline, setOutline] = useState<OutlineData | null>(null);
  const [project, setProject] = useState<ProjectMetadata | null>(null);
  const [projectPhase, setProjectPhase] = useState<ProjectPhase | null>(null);
  const [yamlText, setYamlText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const isInitialMount = useRef(true);

  const fetchData = useCallback(async () => {
    if (!projectId) return;
    setIsLoading(true);
    try {
      const [outlineResponse, projectResponse] = await Promise.all([
        fetch(`/api/projects/${projectId}/outline`),
        fetch(`/api/projects/${projectId}`),
      ]);

      if (!outlineResponse.ok) {
        throw new Error(`获取大纲失败: ${outlineResponse.statusText}`);
      }
      if (!projectResponse.ok) {
        throw new Error(`获取项目信息失败: ${projectResponse.statusText}`);
      }

      const outlineData: OutlineData = await outlineResponse.json();
      const projectData: ProjectMetadata = await projectResponse.json();

      setOutline(outlineData);
      setProject(projectData);
      setProjectPhase(projectData.phase);
      setYamlText(YAML.stringify(outlineData));
      setSaveStatus("success");
    } catch (e) {
      if (e instanceof Error) setError(e.message);
    } finally {
      setIsLoading(false);
    }
  }, [projectId]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const handleAutoSave = useCallback(
    async (textToSave: string) => {
      if (!projectId || projectPhase !== ProjectPhase.OUTLINE) return;
      setSaveStatus("saving");

      try {
        const parsedData = YAML.parse(textToSave);
        if (!isValidOutlineData(parsedData)) {
          throw new Error("YAML 结构或类型错误. 必须包含 'title' 和 'plots'.");
        }

        const response = await fetch(`/api/projects/${projectId}/outline`, {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(parsedData),
        });

        if (!response.ok) {
          throw new Error("保存至服务器失败");
        }

        setOutline(parsedData);
        setSaveStatus("success");
      } catch (e) {
        console.error(e);
        setSaveStatus("error");
      }
    },
    [projectId, projectPhase],
  );

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }
    if (projectPhase !== ProjectPhase.OUTLINE) return;

    const debounceTimer = setTimeout(() => {
      handleAutoSave(yamlText);
    }, 150);

    return () => clearTimeout(debounceTimer);
  }, [yamlText, handleAutoSave, projectPhase]);

  const handleEditorChange = (value: string | undefined) => {
    if (saveStatus === "success" || saveStatus === "error") {
      setSaveStatus("idle");
    }
    setYamlText(value || "");
  };

  const handleAdvancePhase = async () => {
    if (!projectId || !project || saveStatus !== "success") {
      alert("请确保所有更改已成功保存后再进入下一阶段。");
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
          phase: ProjectPhase.WORLD_SETUP,
        }),
      });

      if (!response.ok) {
        throw new Error("推进项目阶段失败");
      }

      // 推进成功后，导航到新阶段的页面
      navigate(`/projects/${projectId}/world-setup`);
      window.location.reload(); // 刷新以确保侧边栏等状态正确更新
    } catch (err) {
      if (err instanceof Error) {
        setError(err.message);
      }
    }
  };

  if (isLoading) {
    return <div>正在加载大纲...</div>;
  }

  if (error) {
    return <div className="text-red-500">错误: {error}</div>;
  }

  const isReadOnly = projectPhase !== ProjectPhase.OUTLINE;

  const SaveStatusIndicator = () => (
    <div className="flex items-center gap-2 text-sm text-muted-foreground w-40 justify-end">
      {" "}
      {/* 增加了宽度到 w-40 */}
      {isReadOnly ? (
        <span>（只读模式）</span>
      ) : (
        <>
          {saveStatus === "saving" && (
            <>
              <Loader2 className="size-4 animate-spin" />
              <span>正在保存...</span>
            </>
          )}
          {saveStatus === "success" && (
            <>
              <Check className="size-4 text-green-500" />
              <span>已保存</span>
            </>
          )}
          {saveStatus === "error" && (
            <>
              <AlertCircle className="size-4 text-red-500" />
              <span>格式或结构错误</span>
            </>
          )}
        </>
      )}
    </div>
  );

  return (
    <div className="flex flex-col h-full gap-4">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">
            {outline ? outline.title : "大纲设计"}
          </h1>
          <p className="mt-2 text-muted-foreground">
            当前正在编辑的项目 ID: {projectId}
          </p>
        </div>
        <div className="flex items-center gap-4">
          <SaveStatusIndicator />
          {projectPhase === ProjectPhase.OUTLINE && (
            <Button
              onClick={handleAdvancePhase}
              disabled={saveStatus !== "success"}
              title="确保所有修改都已保存后再继续"
            >
              <span>完成大纲</span>
              <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
      <div className="flex-1 min-h-0 border rounded-md overflow-hidden shadow-sm">
        <Editor
          language="yaml"
          theme="vs-dark"
          value={yamlText}
          onChange={handleEditorChange}
          options={{
            readOnly: isReadOnly,
            minimap: { enabled: false },
            fontSize: 14,
            wordWrap: "on",
            padding: { top: 16 },
            scrollBeyondLastLine: false,
          }}
        />
      </div>
    </div>
  );
}

export default OutlinePage;
