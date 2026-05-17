import type {
  ChatRequest,
  ChatStreamEvent,
  OccupancyResponse,
  PredictionResult,
  ZoneResponse,
} from "./types";

function getApiBase(): string {
  const url = import.meta.env.VITE_API_URL || "";
  if (!url) return "";
  if (url.startsWith("http://") || url.startsWith("https://")) return url;
  return `https://${url}`;
}

const API_BASE = getApiBase();

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function parseJson<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function getOccupancy(): Promise<OccupancyResponse[]> {
  const res = await fetch(`${API_BASE}/api/occupancy`);
  return parseJson<OccupancyResponse[]>(res);
}

export async function getPredict(
  location: string,
  targetDatetimeIso: string,
): Promise<PredictionResult> {
  const params = new URLSearchParams({
    location,
    target_datetime: targetDatetimeIso,
  });
  const res = await fetch(`${API_BASE}/api/predict?${params}`);
  return parseJson<PredictionResult>(res);
}

export async function getZones(street: string): Promise<ZoneResponse> {
  const params = new URLSearchParams({ street });
  const res = await fetch(`${API_BASE}/api/zones?${params}`);
  return parseJson<ZoneResponse>(res);
}

export async function getStreets(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/api/zones/streets`);
  return parseJson<string[]>(res);
}

export async function postChatStream(
  body: ChatRequest,
  onEvent: (ev: ChatStreamEvent) => void,
): Promise<void> {
  const res = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    throw new ApiError(res.status, await res.text());
  }
  const reader = res.body?.getReader();
  if (!reader) throw new Error("No response body");
  const decoder = new TextDecoder();
  let carry = "";
  const flushBlock = (block: string) => {
    const trimmed = block.trim();
    if (!trimmed) return;
    for (const line of trimmed.split("\n")) {
      if (!line.startsWith("data:")) continue;
      const raw = line.slice(5).trim();
      try {
        onEvent(JSON.parse(raw) as ChatStreamEvent);
      } catch {
        /* ignore malformed chunk */
      }
    }
  };
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    carry += decoder.decode(value, { stream: true });
    const parts = carry.split("\n\n");
    carry = parts.pop() ?? "";
    for (const p of parts) flushBlock(p);
  }
  if (carry.trim()) flushBlock(carry);
}
