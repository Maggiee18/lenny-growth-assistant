import type { SourceCitation } from "@/lib/types";

export function SourceCard({ source }: { source: SourceCitation }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3 text-sm shadow-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="truncate font-medium text-slate-800">{source.title}</p>
          {source.episode && <p className="text-xs text-slate-500">{source.episode}</p>}
        </div>
        <span
          className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-600"
          title="Retrieval relevance score"
        >
          {(source.relevance_score * 100).toFixed(0)}%
        </span>
      </div>
      <p className="mt-2 line-clamp-3 text-xs text-slate-500">&ldquo;{source.excerpt}&rdquo;</p>
      {source.source_url && (
        <a
          href={source.source_url}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-2 inline-block text-xs font-medium text-brand-600 hover:underline"
        >
          View source ↗
        </a>
      )}
    </div>
  );
}
