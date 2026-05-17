/** Mirrors backend Pydantic models (app/models.py + prediction dict). */

export type DataSource = "tfnsw" | "simulated";

export interface OccupancyResponse {
  car_park_id: string;
  name: string;
  occupancy_pct: number;
  occupied: number;
  available: number;
  capacity: number;
  lat: number;
  lon: number;
  source: DataSource;
  as_of: string;
}

export interface PredictionResult {
  car_park_id: string;
  name: string;
  predicted_occupancy_pct: number;
  confidence: number;
  target_datetime: string;
  model_version: string;
}

export interface RestrictionRule {
  days: string[];
  start: string;
  end: string;
  max_minutes: number | null;
  type:
    | "no_stopping"
    | "no_parking"
    | "timed"
    | "permit_only"
    | "loading"
    | "other";
}

export interface ZoneSegment {
  side: string | null;
  rules_plain_english: string;
  rules_structured: RestrictionRule[];
  sign_photo_url: string | null;
}

export interface ZoneResponse {
  street: string;
  segments: ZoneSegment[];
}

export interface ChatRequest {
  message: string;
  history: { role: "user" | "assistant"; content: string }[];
}

export type ChatStreamEvent =
  | { type: "text"; content: string }
  | { type: "tool_call"; tool: string; input: Record<string, unknown> }
  | { type: "tool_result"; tool: string; result: Record<string, unknown> }
  | { type: "error"; message: string }
  | { type: "done" };

export type MarkerData = {
  id: string;
  name: string;
  lat: number;
  lon: number;
  pct: number;
  source: DataSource;
  mode: "live" | "predicted";
  confidence?: number;
  modelVersion?: string;
  /** When predict API failed for this park in predicted mode */
  predictionMissing?: boolean;
  /** Map markers still show live % while parallel predict calls are in flight */
  predictionPending?: boolean;
  /** From last occupancy snapshot — for detail bar */
  capacity?: number;
  occupied?: number;
  available?: number;
  /** ISO datetime string for predictions */
  targetDatetime?: string;
};

export type ToolName = "get_live_occupancy" | "predict_availability" | "get_zone_restrictions";

export interface ToolCardConfig {
  label: string;
  color: string;
  bgTint: string;
  borderColor: string;
}
