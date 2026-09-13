import type { SessionSummary } from "@/lib/types";

export function Sidebar({
  sessions,
  activeSessionId,
  onSelect,
  onNewChat,
  loading,
}: {
  sessions: SessionSummary[];
  activeSessionId: string | null;
  onSelect: (id: string) => void;
  onNewChat: () => void;
  loading: boolean;
}) {
  return (
    <nav className="flex h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-white" aria-label="Chat sessions">
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white hover:bg-brand-700"
        >
          + New chat
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {loading && sessions.length === 0 && (
          <p className="px-2 py-4 text-xs text-slate-400">Loading sessions…</p>
        )}
        {!loading && sessions.length === 0 && (
          <p className="px-2 py-4 text-xs text-slate-400">No chats yet. Start one above.</p>
        )}
        <ul className="space-y-0.5">
          {sessions.map((s) => (
            <li key={s.id}>
              <button
                onClick={() => onSelect(s.id)}
                aria-current={s.id === activeSessionId ? "page" : undefined}
                className={`w-full truncate rounded-lg px-3 py-2 text-left text-sm ${
                  s.id === activeSessionId
                    ? "bg-brand-50 font-medium text-brand-700"
                    : "text-slate-600 hover:bg-slate-50"
                }`}
              >
                {s.title}
                <span className="ml-1 text-xs text-slate-400">({s.message_count})</span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}
