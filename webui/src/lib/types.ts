export interface ChapterInfo {
  title: string;
  intent: string;
}

export interface ChapterInfos {
  chapters: ChapterInfo[];
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  type?: "thinking" | "tool_result" | "final";
}

export interface OutlineData {
  title: string;
  plots: string[];
}

export type GroupedMessage =
  | Message
  | { type: "tool_group"; messages: Message[]; id: string };
