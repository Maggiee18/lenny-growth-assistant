"use client";

import { useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { ArtifactOut } from "@/lib/types";

/**
 * Security model (see docs/design.md "Artifact viewer" and
 * backend/app/skills/artifacts/sanitizer.py for the server-side layer):
 *
 * - Markdown artifacts render through react-markdown with NO rehype-raw
 *   plugin, so any raw HTML embedded in the markdown string is displayed as
 *   literal escaped text, never parsed as markup. There is no
 *   dangerouslySetInnerHTML anywhere in this component.
 * - HTML artifacts are already sanitized server-side (scripts, event
 *   handlers, iframes/objects/embeds/forms, javascript: URLs, and external
 *   resource loading beyond http(s) images/links are stripped before this
 *   component ever sees the string). This component adds a second,
 *   independent layer: the sanitized HTML is rendered inside an <iframe
 *   sandbox> with an EMPTY sandbox attribute -- the most restrictive
 *   setting. That disables script execution, form submission, top-level
 *   navigation, popups, and same-origin access (no cookies/localStorage/
 *   parent-DOM access) unconditionally, so even a sanitizer bypass cannot
 *   execute code or reach the rest of the app.
 * - We deliberately do NOT add `allow-scripts` or `allow-same-origin` to the
 *   sandbox. Generated artifacts never need to run JavaScript; if a future
 *   requirement needs interactivity, that decision should be revisited
 *   explicitly rather than loosened by default.
 */

function buildIframeDocument(sanitizedHtmlFragment: string, title: string): string {
  const escapedTitle = title.replace(/[<>&]/g, (c) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;" }[c]!));
  return `<!doctype html><html><head><meta charset="utf-8"><title>${escapedTitle}</title>
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src https: data:; style-src 'unsafe-inline'; font-src https:;">
<style>body{font-family:system-ui,-apple-system,sans-serif;margin:16px;color:#1a1a1a;}img{max-width:100%;}</style>
</head><body>${sanitizedHtmlFragment}</body></html>`;
}

type SourceView = "rendered" | "source";

export function ArtifactViewer({
  artifact,
  onClose,
}: {
  artifact: ArtifactOut | null;
  onClose: () => void;
}) {
  const [view, setView] = useState<SourceView>("rendered");
  const [copied, setCopied] = useState(false);
  const [renderFailed, setRenderFailed] = useState(false);

  const iframeSrcDoc = useMemo(() => {
    if (!artifact || artifact.artifact_type !== "html") return "";
    try {
      return buildIframeDocument(artifact.content, artifact.title);
    } catch {
      return "";
    }
  }, [artifact]);

  if (!artifact) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3 p-8 text-center text-slate-400">
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-brand-50 text-2xl" aria-hidden>
          📄
        </div>
        <p className="text-sm text-slate-500">Artifacts you generate will appear here.</p>
        <p className="max-w-xs text-xs text-slate-400">
          Ask for a Ship 30 essay, a Markdown summary, or an HTML page and it will render alongside the chat.
        </p>
      </div>
    );
  }

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(artifact.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* clipboard API unavailable -- non-critical, silently ignore */
    }
  };

  const handleDownload = () => {
    const ext = artifact.artifact_type === "html" ? "html" : "md";
    const blob = new Blob([artifact.content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${artifact.title.replace(/[^a-z0-9-_]+/gi, "-").toLowerCase() || "artifact"}.${ext}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between gap-2 border-b border-slate-200 bg-white px-4 py-3 shadow-sm">
        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-800">{artifact.title}</p>
          <p className="text-xs uppercase tracking-wide text-slate-400">{artifact.artifact_type}</p>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <div className="mr-2 flex rounded-md border border-slate-200 bg-slate-50 p-0.5 text-xs">
            <button
              className={`rounded px-2 py-1 transition-colors ${view === "rendered" ? "bg-brand-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
              onClick={() => setView("rendered")}
              aria-pressed={view === "rendered"}
            >
              Rendered
            </button>
            <button
              className={`rounded px-2 py-1 transition-colors ${view === "source" ? "bg-brand-600 text-white shadow-sm" : "text-slate-600 hover:text-slate-900"}`}
              onClick={() => setView("source")}
              aria-pressed={view === "source"}
            >
              Source
            </button>
          </div>
          <button
            onClick={handleCopy}
            className={`rounded-md border px-2 py-1 text-xs font-medium transition-colors ${
              copied
                ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                : "border-slate-200 text-slate-600 hover:bg-slate-50"
            }`}
          >
            {copied ? "✓ Copied" : "Copy"}
          </button>
          <button
            onClick={handleDownload}
            className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            Download
          </button>
          <button
            onClick={onClose}
            aria-label="Close artifact viewer"
            className="rounded-md border border-slate-200 px-2 py-1 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50"
          >
            Close
          </button>
        </div>
      </div>

      <div className="min-h-0 flex-1 overflow-auto bg-slate-50">
        {renderFailed ? (
          <div className="p-6 text-sm text-red-600">Unable to safely render this artifact.</div>
        ) : view === "source" ? (
          <pre className="h-full overflow-auto whitespace-pre-wrap p-4 text-xs text-slate-700">{artifact.content}</pre>
        ) : artifact.artifact_type === "html" ? (
          <iframe
            key={artifact.id}
            title={artifact.title}
            srcDoc={iframeSrcDoc}
            sandbox=""
            referrerPolicy="no-referrer"
            className="h-full w-full border-0 bg-white"
            onError={() => setRenderFailed(true)}
          />
        ) : (
          <div className="markdown-body h-full overflow-auto bg-white p-6">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{artifact.content}</ReactMarkdown>
          </div>
        )}
      </div>
    </div>
  );
}
