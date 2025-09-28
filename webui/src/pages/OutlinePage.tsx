import { useState, useEffect, useCallback, useRef } from "react";
import { useParams } from "react-router-dom";
import YAML from "yaml";
import Editor from "@monaco-editor/react";
import { Loader2, Check, AlertCircle } from "lucide-react";

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

  const [outline, setOutline] = useState<OutlineData | null>(null);
  const [yamlText, setYamlText] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");
  const isInitialMount = useRef(true);

  useEffect(() => {
    if (!projectId) return;

    const fetchOutline = async () => {
      try {
        const response = await fetch(`/api/projects/${projectId}/outline`);
        if (!response.ok) {
          throw new Error(`获取大纲失败: ${response.statusText}`);
        }
        const data: OutlineData = await response.json();
        setOutline(data);
        setYamlText(YAML.stringify(data));
        setSaveStatus("success"); // 初始数据加载完毕，视为已保存
      } catch (e) {
        if (e instanceof Error) setError(e.message);
      } finally {
        setIsLoading(false);
      }
    };

    fetchOutline();
  }, [projectId]);

  const handleAutoSave = useCallback(
    async (textToSave: string) => {
      if (!projectId) return;
      setSaveStatus("saving");

      try {
        const parsedData = YAML.parse(textToSave);

        // 在此处进行类型验证
        if (!isValidOutlineData(parsedData)) {
          throw new Error(
            "YAML 结构或类型错误. 必须包含字符串 'title' 和字符串数组 'plots'.",
          );
        }

        const response = await fetch(`/api/projects/${projectId}/outline`, {
          method: "POST",
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
    [projectId],
  );

  useEffect(() => {
    if (isInitialMount.current) {
      isInitialMount.current = false;
      return;
    }

    // 防抖处理：在用户停止输入 150ms 后再触发保存
    const debounceTimer = setTimeout(() => {
      handleAutoSave(yamlText);
    }, 150);

    return () => clearTimeout(debounceTimer);
  }, [yamlText, handleAutoSave]);

  const handleEditorChange = (value: string | undefined) => {
    // 当用户输入时，如果当前状态是成功或失败，则立即重置为空闲
    if (saveStatus === "success" || saveStatus === "error") {
      setSaveStatus("idle");
    }
    setYamlText(value || "");
  };

  if (isLoading) {
    return <div>正在加载大纲...</div>;
  }

  if (error) {
    return <div className="text-red-500">错误: {error}</div>;
  }

  const SaveStatusIndicator = () => (
    <div className="flex items-center gap-2 text-sm text-muted-foreground w-36 justify-end">
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
        <SaveStatusIndicator />
      </div>
      <div className="flex-1 min-h-0 border rounded-md overflow-hidden shadow-sm">
        <Editor
          language="yaml"
          theme="vs-dark"
          value={yamlText}
          onChange={handleEditorChange}
          options={{
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
