export interface ToolExecution {
  tool_name: string;
  goal?: string;
  result?: unknown;
  explanation?: string;
  title?: string;
  video_id?: string;
  views?: number;
  [key: string]: unknown;
}
