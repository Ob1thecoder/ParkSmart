import { useMemo } from "react";
import { Marker } from "react-map-gl/maplibre";
import type { MarkerData } from "../../types";
import { occupancyColor } from "../../lib/occupancy";

type Props = {
  data: MarkerData;
  isSkeleton?: boolean;
  onClick: () => void;
};

export function CarParkMarker({ data, isSkeleton, onClick }: Props) {
  const markerStyle = useMemo(() => {
    if (isSkeleton) {
      return {
        background: "rgba(148,163,184,0.5)",
        border: "none",
        color: "transparent",
        label: "",
        animate: true,
      };
    }

    if (data.predictionPending) {
      return {
        background: "rgba(255,255,255,0.95)",
        border: "2px dashed #7c3aed",
        color: "#5b21b6",
        label: "…",
        animate: true,
        shadow: "0 2px 12px rgba(124,58,237,0.35)",
      };
    }

    const fill = data.predictionMissing ? "#94a3b8" : occupancyColor(data.pct);
    const outlined = data.source === "simulated";
    const label = data.predictionMissing ? "—" : `${Math.round(data.pct * 100)}`;
    const bg = outlined && !data.predictionMissing ? "#fff" : fill;
    const border = outlined
      ? `3px solid ${fill}`
      : "2px solid rgba(12,26,20,0.2)";
    const fg = outlined && !data.predictionMissing ? fill : "#fff";

    return {
      background: bg,
      border,
      color: fg,
      label,
      animate: false,
      shadow: "0 2px 10px rgba(12,26,20,0.28)",
    };
  }, [data.pct, data.source, data.predictionMissing, data.predictionPending, isSkeleton]);

  return (
    <Marker
      longitude={data.lon}
      latitude={data.lat}
      anchor="center"
      onClick={(e) => {
        e.originalEvent.stopPropagation();
        onClick();
      }}
    >
      <div
        className={`park-marker ${markerStyle.animate ? "animate-marker-pulse" : ""}`}
        style={{
          width: isSkeleton ? 20 : data.predictionPending ? 30 : 28,
          height: isSkeleton ? 20 : data.predictionPending ? 30 : 28,
          borderRadius: "50%",
          background: markerStyle.background,
          border: markerStyle.border,
          boxShadow: markerStyle.shadow || "0 2px 10px rgba(12,26,20,0.28)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          cursor: isSkeleton ? "default" : "pointer",
          transition: "transform 0.15s ease, box-shadow 0.15s ease",
        }}
      >
        <span
          style={{
            fontFamily: "'DM Sans', system-ui, sans-serif",
            fontWeight: 700,
            fontSize: data.predictionPending ? 11 : 10,
            lineHeight: 1,
            color: markerStyle.color,
          }}
        >
          {markerStyle.label}
        </span>
      </div>
    </Marker>
  );
}
