import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { MessageOut, SourceCitation } from "@/lib/types";
import { SourceCard } from "./SourceCard";

export function MessageBubble({
  message,
  sources,
  abstained,
  onOpenArtifact,
  hasArtifact,
}: {
  message: MessageOut;
  sources?: SourceCitation[];
  abstained?: boolean;
  hasArtifact?: boolean;
  onOpenArtifact?: () => void;
}) {
  const isUser = message.role === "user";

  return (
    <div className={`flex items-start gap-2.5 ${isUser ? "justify-end" : "justify-start"}`}>
      {!isUser && (
        <div
          className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-brand-600 text-xs font-semibold text-white"
          aria-hidden
        >
          L
        </div>
      )}
      <div className={`max-w-[75ch] ${isUser ? "" : "min-w-0 flex-1"}`}>
        <div
          className={`rounded-2xl px-4 py-3 text-sm shadow-sm ${
            isUser
              ? "bg-brand-600 text-white"
              : abstained
                ? "border border-amber-200 bg-amber-50 text-amber-900"
                : "border border-slate-200 bg-white text-slate-800"
          }`}
        >
          {isUser ? (
            <p className="whitespace-pre-wrap">{message.content}</p>
          ) : (
            <div className="markdown-body">
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
            </div>
          )}
        </div>

        {hasArtifact && onOpenArtifact && (
          <button
            onClick={onOpenArtifact}
            className="mt-2 inline-flex items-center gap-1.5 rounded-md border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-700"
          >
            📄 Open artifact
          </button>
        )}

        {sources && sources.length > 0 && (
          <div className="mt-3 space-y-2">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-400">Sources</p>
            <div className="grid gap-2 sm:grid-cols-2">
              {sources.map((s) => (
                <SourceCard key={s.chunk_id} source={s} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
