import type { ChatToolEntry } from "../../context/ChatContext";

function describe(tool: string, input: Record<string, unknown>): string {
  const str = (k: string): string | undefined =>
    typeof input[k] === "string" ? (input[k] as string) : undefined;
  const location = str("location");
  const street = str("street");
  const when = str("target_datetime");

  if (tool === "get_live_occupancy") {
    return location
      ? `Checking live occupancy near ${location}`
      : "Checking live occupancy";
  }
  if (tool === "predict_availability") {
    let label = location
      ? `Predicting availability near ${location}`
      : "Predicting availability";
    if (when) {
      const d = new Date(when);
      if (!Number.isNaN(d.getTime())) {
        label += ` for ${d.toLocaleString("en-AU", {
          weekday: "short",
          hour: "numeric",
          minute: "2-digit",
        })}`;
      }
    }
    return label;
  }
  if (tool === "get_zone_restrictions") {
    return street
      ? `Looking up parking rules for ${street}`
      : "Looking up street parking rules";
  }
  return tool;
}

export function ToolCallBadge({ tool, input }: ChatToolEntry) {
  return (
    <div className="mt-2 flex items-center gap-1.5 rounded-lg border border-teal-200 bg-teal-50 px-2 py-1.5 text-[11px] text-teal-900">
      <span aria-hidden>⚙</span>
      <span className="font-medium">{describe(tool, input)}</span>
    </div>
  );
}
