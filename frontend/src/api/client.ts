const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8000/api/v1";
const API_KEY = import.meta.env.VITE_API_KEY ?? "dev-api-key-change-in-prod";

export async function apiGet<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "X-API-KEY": API_KEY
    }
  });

  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }

  return (await response.json()) as T;
}

export async function apiPost<T>(path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { "X-API-KEY": API_KEY };
  const init: RequestInit = { method: "POST", headers };

  if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }

  const response = await fetch(`${API_BASE}${path}`, init);

  if (!response.ok) {
    throw new Error(`Request failed (${response.status})`);
  }

  return (await response.json()) as T;
}

export async function fetchDocumentBlob(documentId: number): Promise<Blob> {
  const response = await fetch(`${API_BASE}/documents/${documentId}/file`, {
    headers: {
      "X-API-KEY": API_KEY
    }
  });

  if (!response.ok) {
    throw new Error(`Unable to load document (${response.status})`);
  }

  return response.blob();
}