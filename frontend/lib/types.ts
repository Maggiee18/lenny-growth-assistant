export type Role = "user" | "assistant" | "system";

export interface SourceCitation {
  document_id: string;
  chunk_id: string;
  title: string;
  episode: string | null;
  source_url: string | null;
  excerpt: string;
  relevance_score: number;
}

export interface MessageOut {
  id: string;
  session_id: string;
  role: Role;
  content: string;
  message_metadata: Record<string, unknown>;
  created_at: string;
}

export interface SessionSummary {
  id: string;
  title: string;
  provider: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

export interface SessionDetail extends SessionSummary {
  messages: MessageOut[];
}

export interface MessageResponse {
  user_message: MessageOut;
  assistant_message: MessageOut;
  sources: SourceCitation[];
  abstained: boolean;
  artifact_id: string | null;
  provider: string;
  model: string;
}

export type ArtifactType = "markdown" | "html" | "ship30";

export interface ArtifactOut {
  id: string;
  session_id: string | null;
  message_id: string | null;
  artifact_type: ArtifactType;
  title: string;
  content: string;
  artifact_metadata: Record<string, unknown>;
  created_at: string;
}

export interface ConfigResponse {
  provider: string;
  model: string;
  ollama_available: boolean;
  anthropic_configured: boolean;
  retrieval_top_k: number;
  retrieval_similarity_threshold: number;
}

export interface HealthDependency {
  name: string;
  healthy: boolean;
  detail: string | null;
}

export interface HealthResponse {
  status: "ok" | "degraded" | "down";
  dependencies: HealthDependency[];
}

export interface ApiErrorBody {
  error: {
    category: string;
    message: string;
    detail: string | null;
  };
}
