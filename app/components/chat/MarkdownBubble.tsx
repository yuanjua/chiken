"use client";

import React, { Children, Fragment, useState, useCallback, useEffect, useRef } from "react";
// 1. Import the 'Components' type from the library
import ReactMarkdown, { type Components } from "react-markdown";
import { open } from "@tauri-apps/plugin-shell";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import rehypeRaw from "rehype-raw";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { vscDarkPlus } from "react-syntax-highlighter/dist/esm/styles/prism";
import "katex/dist/katex.min.css";
import { Button } from "@/components/ui/button";
import { findAllTables, extractTableToData } from "@/lib/dom-table";
import { SearchTableDialog } from "./SearchTableDialog";
import { useTranslations } from "next-intl";

// --- CodeBlock Component ---
const CodeBlock = React.memo(
  ({
    className,
    children,
  }: {
    className?: string;
    children?: React.ReactNode;
  }) => {
    const [isCopied, setIsCopied] = useState(false);
    const match = /language-(\w+)/.exec(className || "");
    const language = match ? match[1] : "text";
    const codeText = String(children).replace(/\n$/, "");

    const handleCopy = useCallback(() => {
      const nav = (globalThis as any).navigator as Navigator | undefined;
      if (nav && nav.clipboard) {
        nav.clipboard.writeText(codeText).then(
          () => {
            setIsCopied(true);
            setTimeout(() => setIsCopied(false), 2000);
          },
          () => {
            setIsCopied(false);
          }
        );
      } else {
        setIsCopied(false);
      }
    }, [codeText]);

    if (!className?.includes("language-")) {
      return (
        <code className="bg-gray-200 dark:bg-gray-700 text-red-500 dark:text-red-400 px-1 py-0.5 rounded-md text-sm font-mono">
          {children}
        </code>
      );
    }

    return (
      <div className="rounded-lg bg-[#1e1e1e] text-sm relative group overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-gray-700">
          <span className="text-gray-400 text-xs font-sans">{language}</span>
          <button
            onClick={handleCopy}
            className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 text-white rounded-md transition-all duration-200"
          >
            {isCopied ? "Copied!" : "Copy"}
          </button>
        </div>
        <div className="overflow-x-auto max-w-full">
          <SyntaxHighlighter
            style={vscDarkPlus}
            language={language}
            PreTag="div"
            customStyle={{
              margin: 0,
              padding: "0.8rem",
              background: "transparent",
              maxWidth: "100%",
              overflow: "auto",
            }}
            codeTagProps={{
              style: {
                fontFamily:
                  'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace',
                fontSize: "13px",
                wordBreak: "break-all",
                whiteSpace: "pre-wrap",
              },
            }}
          >
            {codeText}
          </SyntaxHighlighter>
        </div>
      </div>
    );
  },
);
CodeBlock.displayName = "CodeBlock";

// --- Style Definitions ---
const componentStyles = {
  h1: "text-xl font-bold pb-2 border-b border-gray-200 dark:border-gray-700",
  h2: "text-lg font-semibold",
  h3: "text-base font-semibold",
  p: "leading-relaxed",
  ul: "list-disc list-outside pl-5 space-y-1.5",
  ol: "list-decimal list-outside pl-5 space-y-1.5",
  li: "leading-relaxed",
  a: "text-blue-500 hover:underline",
  blockquote:
    "border-l-4 border-gray-300 dark:border-gray-600 pl-3 italic py-1 bg-gray-50 dark:bg-gray-800/50 rounded-r-md",
  thead: "bg-gray-50 dark:bg-gray-800",
  th: "px-3 py-2 text-left font-semibold text-sm border-b border-gray-200 dark:border-gray-700",
  td: "px-3 py-2 text-sm border-b border-gray-200 dark:border-gray-700",
  strong: "font-semibold",
  em: "italic",
};

const handleLinkClick = (e: React.MouseEvent<HTMLAnchorElement>) => {
  e.preventDefault();
  const href = e.currentTarget.href;
  if (href.startsWith("http://") || href.startsWith("https://")) {
    open(href);
  }
};

// --- Main Markdown Component Definitions ---
const markdownComponents: Components = {
  h1: ({ node, ...props }) => <h1 className={componentStyles.h1} {...props} />,
  h2: ({ node, ...props }) => <h2 className={componentStyles.h2} {...props} />,
  h3: ({ node, ...props }) => <h3 className={componentStyles.h3} {...props} />,
  p: ({ node, ...props }) => <p className={componentStyles.p} {...props} />,
  ul: ({ node, ...props }) => <ul className={componentStyles.ul} {...props} />,
  ol: ({ node, ...props }) => <ol className={componentStyles.ol} {...props} />,
  a: ({ node, ...props }) => (
    <a className={componentStyles.a} onClick={handleLinkClick} {...props} />
  ),
  blockquote: ({ node, ...props }) => (
    <blockquote className={componentStyles.blockquote} {...props} />
  ),
  thead: ({ node, ...props }) => (
    <thead className={componentStyles.thead} {...props} />
  ),
  th: ({ node, ...props }) => <th className={componentStyles.th} {...props} />,
  td: ({ node, ...props }) => <td className={componentStyles.td} {...props} />,
  strong: ({ node, ...props }) => (
    <strong className={componentStyles.strong} {...props} />
  ),
  em: ({ node, ...props }) => <em className={componentStyles.em} {...props} />,
  hr: () => <hr className="border-gray-200 dark:border-gray-700" />,
  code: CodeBlock,
  table: ({ node, ...props }) => (
    <div className="overflow-x-auto rounded-lg border border-gray-200 dark:border-gray-700 max-w-full">
      <table className="w-full min-w-full" {...props} />
    </div>
  ),
  // This logic prevents nested <p> tags inside <li> from breaking indentation
  li: ({ node, children, ...props }) => {
    // We check if any child is a paragraph element.
    const isLoose =
      Array.isArray(children) &&
      children.some(
        (child) =>
          React.isValidElement(child) && (child.type as any)?.name === "p",
      );

    // If the list is loose, we unwrap the children from the <p> tag.
    const content = isLoose
      ? Children.map(children, (child) => {
          // 3. FIX: Specify the expected props shape for `isValidElement`.
          if (
            React.isValidElement<{ children: React.ReactNode }>(child) &&
            (child.type as any)?.name === "p"
          ) {
            return <Fragment>{child.props.children}</Fragment>;
          }
          return child;
        })
      : children;

    return (
      <li className={componentStyles.li} {...props}>
        {content}
      </li>
    );
  },
};

// --- The Main Markdown Renderer Component ---
interface MarkdownTextProps {
  content: string;
  className?: string;
}

const MarkdownText = React.memo(
  ({ content, className = "" }: MarkdownTextProps) => {
    const t = (globalThis as any).nextIntl?.t || (()=>undefined);
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [hasTable, setHasTable] = useState(false);
    const [showExport, setShowExport] = useState(false);
    const [dialogData, setDialogData] = useState<{ headers: string[]; records: Array<Record<string, string>> } | null>(null);

    useEffect(() => {
      const el = containerRef.current;
      setHasTable(!!el?.querySelector("table"));
    }, [content]);

    const openExport = () => {
      const container = containerRef.current;
      if (!container) return;
      const tables = findAllTables(container);
      if (tables.length === 0) return;
      const { headers, records } = extractTableToData(tables[0]);
      setDialogData({ headers, records });
      setShowExport(true);
    };

    return (
      // `space-y-3` provides tighter global spacing
      <div
        ref={containerRef}
        className={`markdown-container w-full break-words space-y-3 overflow-hidden ${className}`}
      >
        <style>{`
                .markdown-container .katex-display {
                    overflow-x: auto;
                    overflow-y: hidden;
                    padding: 0.5rem 0;
                    max-width: 100%;
                }
                .markdown-container pre {
                    max-width: 100% !important;
                    overflow-x: auto !important;
                }
                /* Ensure table head dark mode styles work with higher specificity */
                .markdown-container thead {
                    background-color: rgb(249 250 251) !important;
                }
                .dark .markdown-container thead {
                    background-color: rgb(31 41 55) !important;
                }
            `}</style>
        <ReactMarkdown
          remarkPlugins={[remarkGfm, remarkMath]}
          rehypePlugins={[
            rehypeRaw,
            [rehypeKatex, { throwOnError: false, errorColor: "#e74c3c" }],
          ]}
          components={markdownComponents}
        >
          {content}
        </ReactMarkdown>
        {hasTable && (
          <div className="pt-1">
            <Button
              variant="ghost"
              size="sm"
              className="h-6 px-2 text-xs text-muted-foreground"
              onClick={openExport}
            >
              {t("Common.export") || "Export"}
            </Button>
            <SearchTableDialog
              open={showExport}
              onOpenChange={setShowExport}
              headers={dialogData?.headers || []}
              records={dialogData?.records || []}
            />
          </div>
        )}
      </div>
    );
  },
);
MarkdownText.displayName = "MarkdownText";
export default MarkdownText;
