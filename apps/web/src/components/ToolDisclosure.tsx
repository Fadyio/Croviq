import React, { useState } from "react";
import { ChevronDown, ChevronRight, Wrench } from "lucide-react";

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

interface ToolDisclosureProps {
  toolExecutions?: ToolExecution[];
  structuredArtifact?: Record<string, unknown> | null;
}

function getFriendlyToolName(toolName: string): string {
  switch (toolName) {
    case "channel_analytics_inspection":
      return "Channel analytics";
    case "python_code_execution":
      return "Python code execution";
    case "scenario_projection_modeling":
      return "Scenario projection";
    case "channel_interest_profile_match":
      return "Topic profile match";
    default:
      return toolName.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
  }
}

function getFriendlyToolData(tool: ToolExecution): string {
  if (tool.tool_name === "channel_analytics_inspection") {
    return "latest published video + channel baseline";
  }
  if (tool.tool_name === "python_code_execution") {
    return tool.goal || "historical video dataset calculations";
  }
  if (tool.tool_name === "scenario_projection_modeling") {
    return "90-day trajectory modeling";
  }
  if (tool.tool_name === "channel_interest_profile_match") {
    return "channel content pillars + research findings";
  }
  return tool.goal || "channel metrics";
}

export const ToolDisclosure: React.FC<ToolDisclosureProps> = ({
  toolExecutions = [],
  structuredArtifact,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  if (!toolExecutions || toolExecutions.length === 0) {
    return null;
  }

  return (
    <div className="pt-2 border-t border-border-subtle/30 text-xs">
      <div className="flex items-center gap-2 flex-wrap text-text-muted">
        <span className="text-[11px] font-medium text-text-muted">Analysis used</span>
        {toolExecutions.map((tool, idx) => (
          <button
            key={idx}
            type="button"
            onClick={() => setIsOpen(!isOpen)}
            className="inline-flex items-center gap-1 text-[11px] font-medium text-primary hover:text-primary-hover hover:underline transition-colors cursor-pointer"
            title="Toggle tool execution details"
            data-testid={`btn-tool-disclosure-${idx}`}
          >
            {isOpen ? (
              <ChevronDown className="h-3 w-3 shrink-0" />
            ) : (
              <ChevronRight className="h-3 w-3 shrink-0" />
            )}
            <span>{getFriendlyToolName(tool.tool_name)}</span>
          </button>
        ))}
      </div>

      {isOpen && (
        <div
          className="mt-2 space-y-2 rounded-lg bg-surface-3/60 p-3 text-[11px] border border-border-subtle/50 animate-in fade-in"
          data-testid="tool-disclosure-details"
        >
          {toolExecutions.map((tool, idx) => (
            <div key={idx} className="space-y-1">
              <div className="flex items-center gap-1.5 font-mono text-[11px] text-text-primary">
                <Wrench className="h-3 w-3 text-primary shrink-0" />
                <span className="font-semibold">Tool:</span>
                <span className="text-text-secondary">{tool.tool_name}</span>
              </div>
              <div className="text-text-secondary">
                <span className="font-medium text-text-muted">Data: </span>
                <span>{getFriendlyToolData(tool)}</span>
              </div>
              <div className="text-text-secondary">
                <span className="font-medium text-text-muted">Status: </span>
                <span className="text-emerald-400 font-medium">completed</span>
              </div>
            </div>
          ))}

          {structuredArtifact && (
            <div className="pt-2 border-t border-border-subtle/40 text-[10px] text-text-muted">
              <span className="font-semibold uppercase tracking-wider text-primary">
                Artifact: {String(structuredArtifact.type || "Analysis")}
              </span>
            </div>
          )}
        </div>
      )}
    </div>
  );
};
