import React, { useMemo } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export function normalizeMarkdownContent(text: string): string {
  if (!text) return "";

  let out = text;

  // 1. Replace TeX \text{...} with inner text
  out = out.replace(/\\text\{([^}]*)\}/g, "$1");

  // 2. Replace common TeX symbols with Unicode
  out = out.replace(/\\rightarrow/g, "→");
  out = out.replace(/\\leftarrow/g, "←");
  out = out.replace(/\\approx/g, "≈");
  out = out.replace(/\\le(?:q)?(?![a-zA-Z])/g, "≤");
  out = out.replace(/\\ge(?:q)?(?![a-zA-Z])/g, "≥");
  out = out.replace(/\\pm/g, "±");
  out = out.replace(/\\times/g, "×");
  out = out.replace(/\\neq/g, "≠");

  // 3. Replace hypothesis notations $H_1$, $H_0$, H_1, etc.
  const subscriptMap: Record<string, string> = {
    "0": "₀",
    "1": "₁",
    "2": "₂",
    "3": "₃",
    "4": "₄",
    "5": "₅",
    "6": "₆",
    "7": "₇",
    "8": "₈",
    "9": "₉",
  };
  out = out.replace(/\$H_?([0-9])\$/g, (_, d) => `H${subscriptMap[d] || d}`);
  out = out.replace(/\bH_([0-9])\b/g, (_, d) => `H${subscriptMap[d] || d}`);

  // 4. Remove math delimiters around numbers, percentages, currencies, deltas, or simple expressions
  out = out.replace(/(?<!\\)\$\$([^$\n]+?)(?<!\\)\$\$/g, (_, inner) => {
    return inner.replace(/\\([a-zA-Z]+)/g, "$1").trim();
  });
  out = out.replace(/(?<!\\)\$([^$\n]+?)(?<!\\)\$/g, (_, inner) => {
    return inner.replace(/\\([a-zA-Z]+)/g, "$1").trim();
  });

  return out;
}

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = "" }) => {
  const normalizedContent = useMemo(() => normalizeMarkdownContent(content), [content]);

  return (
    <div className={`prose-chat text-xs leading-relaxed text-text-primary ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => (
            <h1 className="mt-3 mb-1.5 text-sm font-bold text-text-primary">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="mt-2.5 mb-1 text-xs font-bold text-text-primary uppercase tracking-wide">
              {children}
            </h2>
          ),
          h3: ({ children }) => (
            <h3 className="mt-2 mb-1 text-xs font-semibold text-text-primary">{children}</h3>
          ),
          p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
          strong: ({ children }) => (
            <strong className="font-semibold text-text-primary">{children}</strong>
          ),
          em: ({ children }) => <em className="italic text-text-secondary">{children}</em>,
          ul: ({ children }) => (
            <ul className="mb-2 list-disc pl-4 space-y-1 last:mb-0">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="mb-2 list-decimal pl-4 space-y-1 last:mb-0">{children}</ol>
          ),
          li: ({ children }) => <li className="leading-relaxed">{children}</li>,
          blockquote: ({ children }) => (
            <blockquote className="my-2 border-l-2 border-primary/60 bg-surface-3/50 px-3 py-1.5 italic text-text-secondary rounded-r">
              {children}
            </blockquote>
          ),
          code: ({ className, children, ...props }) => {
            const isBlock = Boolean(className) || String(children).includes("\n");
            if (isBlock) {
              return (
                <div className="my-2 overflow-x-auto rounded-lg border border-border-subtle bg-surface-3 p-3 font-mono text-[11px] text-text-primary">
                  <pre className="p-0 m-0">
                    <code {...props}>{children}</code>
                  </pre>
                </div>
              );
            }
            return (
              <code
                className="rounded bg-surface-3 px-1.5 py-0.5 font-mono text-[11px] text-primary"
                {...props}
              >
                {children}
              </code>
            );
          },
          table: ({ children }) => (
            <div className="my-2.5 max-w-full overflow-x-auto rounded-lg border border-border-subtle bg-surface-3/40">
              <table className="w-full border-collapse text-[11px] text-left">{children}</table>
            </div>
          ),
          thead: ({ children }) => (
            <thead className="border-b border-border-subtle bg-surface-3/80 text-text-primary font-semibold">
              {children}
            </thead>
          ),
          th: ({ children }) => (
            <th className="px-3 py-2 text-[11px] font-semibold text-text-primary">{children}</th>
          ),
          td: ({ children }) => (
            <td className="border-t border-border-subtle/50 px-3 py-1.5 text-text-secondary">
              {children}
            </td>
          ),
          a: ({ href, children }) => {
            const isExternal = href?.startsWith("http://") || href?.startsWith("https://");
            return (
              <a
                href={href}
                target={isExternal ? "_blank" : undefined}
                rel={isExternal ? "noopener noreferrer" : undefined}
                className="font-medium text-primary underline decoration-primary/40 hover:decoration-primary transition-colors"
              >
                {children}
              </a>
            );
          },
          hr: () => <hr className="my-3 border-border-subtle" />,
        }}
      >
        {normalizedContent}
      </ReactMarkdown>
    </div>
  );
};
