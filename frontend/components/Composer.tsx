"use client";

import { useRef, useState, type KeyboardEvent } from "react";

const SUGGESTIONS = [
  "What do guests say about improving activation?",
  "Write a Ship 30 essay about pricing strategy",
  "Create a markdown one-pager summarizing this conversation",
  "Generate an HTML page about growth loops",
];

export function Composer({
  onSend,
  disabled,
}: {
  onSend: (content: string) => void;
  disabled: boolean;
}) {
  const [value, setValue] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const submit = () => {
    const trimmed = value.trim();
    if (!trimmed || disabled) return;
    onSend(trimmed);
    setValue("");
    textareaRef.current?.focus();
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  return (
    <div className="border-t border-slate-200 bg-white p-3">
      <div className="mx-auto w-full max-w-3xl">
        {value.length === 0 && (
          <div className="mb-2 flex flex-wrap gap-1.5" role="list" aria-label="Suggested prompts">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                role="listitem"
                onClick={() => setValue(s)}
                className="rounded-full border border-slate-200 px-2.5 py-1 text-xs text-slate-500 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-600"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        <div className="flex items-end gap-2">
          <label htmlFor="composer-input" className="sr-only">
            Message
          </label>
          <textarea
            id="composer-input"
            ref={textareaRef}
            value={value}
            onChange={(e) => setValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Ask a product or growth question, or ask for a Ship 30 essay / artifact…"
            rows={1}
            className="max-h-40 flex-1 resize-none rounded-xl border border-slate-300 px-3 py-2.5 text-sm shadow-sm transition-colors focus:border-brand-400"
            disabled={disabled}
          />
          <button
            onClick={submit}
            disabled={disabled || !value.trim()}
            className="rounded-xl bg-brand-600 px-4 py-2.5 text-sm font-medium text-white shadow-sm transition-colors hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-brand-600"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
