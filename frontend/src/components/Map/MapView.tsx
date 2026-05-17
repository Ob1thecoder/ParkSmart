import { useEffect, useMemo, useRef } from "react";
import { MapContainer, TileLayer, Marker, useMap } from "react-leaflet";
import L from "leaflet";
import type { MarkerData } from "../../types";
import type { OccupancyResponse } from "../../types";
import { CarParkMarker } from "./CarParkMarker";

/** Approximate bounds covering Chatswood CBD + Gordon/Lindfield markers */
const DEFAULT_CENTER: [number, number] = [-33.79, 151.175];
const DEFAULT_ZOOM = 12;

const SKELETON_COORDS: [number, number][] = [
  [-33.7972, 151.1825],
  [-33.7964, 151.1799],
  [-33.7992, 151.1804],
  [-33.7975, 151.181],
  [-33.7968, 151.1788],
  [-33.756009, 151.154528],
  [-33.775185, 151.169111],
];

/**
 * Fits the map to the car-park markers once. Re-fits only when the *set* of
 * car parks changes — not on every occupancy poll or time scrub, so the user's
 * pan/zoom is preserved.
 */
function FitBounds({ markers }: { markers: MarkerData[] }) {
  const map = useMap();
  const fittedSig = useRef<string | null>(null);
  useEffect(() => {
    if (markers.length === 0) return;
    const sig = markers
      .map((m) => m.id)
      .slice()
      .sort()
      .join("|");
    if (sig === fittedSig.current) return;
    fittedSig.current = sig;
    const b = L.latLngBounds(
      markers.map((m) => [m.lat, m.lon] as [number, number]),
    );
    map.fitBounds(b, { padding: [48, 48], maxZoom: 13 });
  }, [map, markers]);
  return null;
}

const skIcon = L.divIcon({
  className: "park-marker-wrap",
  html: `<div style="width:20px;height:20px;border-radius:50%;background:rgba(148,163,184,0.5);animation:skeleton-pulse 1.2s ease-in-out infinite"></div>`,
  iconSize: [20, 20],
  iconAnchor: [10, 10],
});

type Props = {
  markers: MarkerData[];
  occupancyRows: OccupancyResponse[] | null;
  loading: boolean;
  loadError: string | null;
  onRetry: () => void;
  isDesktop: boolean;
  viewTime: Date | null;
  predictLoading: boolean;
  onSelectMarker: (id: string) => void;
};

export function MapView({
  markers,
  occupancyRows,
  loading,
  loadError,
  onRetry,
  isDesktop,
  viewTime,
  predictLoading,
  onSelectMarker,
}: Props) {
  const asOfById = useMemo(() => {
    const m = new Map<string, string>();
    occupancyRows?.forEach((r) => m.set(r.car_park_id, r.as_of));
    return m;
  }, [occupancyRows]);

  return (
    <div className="relative h-full w-full bg-park-mist">
      <MapContainer
        center={DEFAULT_CENTER}
        zoom={DEFAULT_ZOOM}
        className="h-full w-full z-0"
        scrollWheelZoom
        zoomControl={false}
      >
        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {markers.length > 0 ? <FitBounds markers={markers} /> : null}
        {loading && !markers.length
          ? SKELETON_COORDS.map((pos, i) => (
              <Marker key={i} position={pos} icon={skIcon} interactive={false} />
            ))
          : null}
        {markers.map((data) => (
          <CarParkMarker
            key={data.id}
            data={data}
            isDesktop={isDesktop}
            asOf={asOfById.get(data.id)}
            viewTime={viewTime}
            onSelect={onSelectMarker}
          />
        ))}
      </MapContainer>

      {predictLoading && viewTime ? (
        <div className="pointer-events-none absolute bottom-36 left-1/2 z-[450] w-[min(92vw,20rem)] -translate-x-1/2 rounded-2xl border border-violet-200 bg-violet-50/95 px-4 py-3 text-center text-sm text-violet-950 shadow-lg md:bottom-24">
          <span className="mr-2 inline-block h-4 w-4 animate-spin rounded-full border-2 border-violet-600 border-t-transparent align-[-2px]" />
          <strong>Calculating predictions</strong>
          <div className="mt-1 text-xs font-normal text-violet-900/90">
            Updating each car park for your selected time…
          </div>
        </div>
      ) : null}

      {loadError ? (
        <div className="absolute bottom-28 left-3 right-3 z-[500] rounded-xl bg-white/95 p-3 text-sm shadow-lg md:bottom-6 md:left-6 md:right-auto md:max-w-sm">
          <p className="font-medium text-park-brick">Could not load live occupancy</p>
          <p className="mt-1 text-park-slate">{loadError}</p>
          <button
            type="button"
            className="mt-2 rounded-lg bg-park-fern px-3 py-1.5 text-xs font-semibold text-white"
            onClick={onRetry}
          >
            Retry
          </button>
        </div>
      ) : null}
    </div>
  );
}
