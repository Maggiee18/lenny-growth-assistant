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
    <nav className="flex h-full w-64 shrink-0 flex-col border-r border-slate-200 bg-slate-50" aria-label="Chat sessions">
      <div className="p-3">
        <button
          onClick={onNewChat}
          className="flex w-full items-center justify-center gap-1.5 rounded-lg bg-brand-600 px-3 py-2 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-700"
        >
          <span aria-hidden>+</span> New chat
        </button>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-3">
        {loading && sessions.length === 0 && (
          <p className="px-3 py-4 text-xs text-slate-400">Loading sessions…</p>
        )}
        {!loading && sessions.length === 0 && (
          <p className="px-3 py-4 text-xs text-slate-400">No chats yet. Start one above.</p>
        )}
        <ul className="space-y-0.5">
          {sessions.map((s) => {
            const active = s.id === activeSessionId;
            return (
              <li key={s.id}>
                <button
                  onClick={() => onSelect(s.id)}
                  aria-current={active ? "page" : undefined}
                  className={`group flex w-full items-center gap-2 rounded-lg border-l-2 px-2.5 py-2 text-left text-sm transition-colors ${
                    active
                      ? "border-brand-600 bg-white font-medium text-brand-700 shadow-sm"
                      : "border-transparent text-slate-600 hover:border-slate-300 hover:bg-white/70"
                  }`}
                >
                  <span className="min-w-0 flex-1 truncate">{s.title}</span>
                  <span
                    className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] tabular-nums ${
                      active ? "bg-brand-50 text-brand-600" : "text-slate-400 group-hover:text-slate-500"
                    }`}
                  >
                    {s.message_count}
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    </nav>
  );
}
