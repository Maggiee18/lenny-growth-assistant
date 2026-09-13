import type {
  ApiErrorBody,
  ArtifactOut,
  ArtifactType,
  ConfigResponse,
  HealthResponse,
  MessageResponse,
  SessionDetail,
  SessionSummary,
} from "./types";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";

export class ApiError extends Error {
  category: string;
  detail: string | null;
  status: number;

  constructor(status: number, body: ApiErrorBody) {
    super(body.error?.message || "Request failed");
    this.status = status;
    this.category = body.error?.category || "internal_error";
    this.detail = body.error?.detail ?? null;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${API_BASE_URL}${path}`, {
      ...init,
      headers: { "Content-Type": "application/json", ...(init?.headers || {}) },
    });
  } catch (err) {
    throw new Error(
      `Could not reach the backend at ${API_BASE_URL}. Is it running? (${(err as Error).message})`
    );
  }

  if (!res.ok) {
    let body: ApiErrorBody;
    try {
      body = await res.json();
    } catch {
      throw new Error(`Request failed with status ${res.status}`);
    }
    throw new ApiError(res.status, body);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  getHealth: () => request<HealthResponse>("/health"),
  getConfig: () => request<ConfigResponse>("/api/config"),

  listSessions: () => request<SessionSummary[]>("/api/sessions"),
  createSession: (title?: string) =>
    request<SessionSummary>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ title }),
    }),
  getSession: (sessionId: string) => request<SessionDetail>(`/api/sessions/${sessionId}`),

  postMessage: (sessionId: string, content: string) =>
    request<MessageResponse>(`/api/sessions/${sessionId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  createArtifact: (sessionId: string, artifactType: ArtifactType, instructions?: string) =>
    request<ArtifactOut>("/api/artifacts", {
      method: "POST",
      body: JSON.stringify({ session_id: sessionId, artifact_type: artifactType, instructions }),
    }),
  getArtifact: (artifactId: string) => request<ArtifactOut>(`/api/artifacts/${artifactId}`),
};
