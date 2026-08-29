import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

export const MarkdownRenderer: React.FC<MarkdownRendererProps> = ({ content, className = "" }) => {
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
        {content}
      </ReactMarkdown>
    </div>
  );
};
