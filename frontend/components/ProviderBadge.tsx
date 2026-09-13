import type { ConfigResponse } from "@/lib/types";

export function ProviderBadge({ config }: { config: ConfigResponse | null }) {
  if (!config) {
    return (
      <span className="inline-flex items-center gap-1.5 rounded-full border border-slate-200 bg-slate-100 px-2.5 py-1 text-xs text-slate-400">
        <span className="h-1.5 w-1.5 rounded-full bg-slate-300" />
        Checking provider…
      </span>
    );
  }

  const isLocal = config.provider === "ollama";
  const healthy = isLocal ? config.ollama_available : config.anthropic_configured;

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${
        healthy
          ? "border-emerald-200 bg-emerald-50 text-emerald-700"
          : "border-amber-200 bg-amber-50 text-amber-700"
      }`}
      title={healthy ? undefined : "Configured provider is unavailable -- check backend health"}
    >
      <span className={`h-1.5 w-1.5 rounded-full ${healthy ? "bg-emerald-500" : "bg-amber-500"}`} />
      {isLocal ? "Local" : "Cloud"} · {isLocal ? "Ollama" : "Anthropic"} · {config.model}
    </span>
  );
}
