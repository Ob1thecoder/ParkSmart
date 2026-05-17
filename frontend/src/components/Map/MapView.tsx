import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import Map, { NavigationControl, Popup } from "react-map-gl/maplibre";
import type { MapRef } from "react-map-gl/maplibre";
import type { LngLatBoundsLike } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
import type { MarkerData, OccupancyResponse } from "../../types";
import { CarParkMarker } from "./CarParkMarker";
import { CarParkDetail } from "./CarParkDetail";

const DEFAULT_CENTER = { longitude: 151.175, latitude: -33.79 };
const DEFAULT_ZOOM = 12;

const SKELETON_COORDS: [number, number][] = [
  [151.1825, -33.7972],
  [151.1799, -33.7964],
  [151.1804, -33.7992],
  [151.181, -33.7975],
  [151.1788, -33.7968],
  [151.154528, -33.756009],
  [151.169111, -33.775185],
];

const MAP_STYLE = "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

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
  const mapRef = useRef<MapRef>(null);
  const fittedSig = useRef<string | null>(null);
  const [popupInfo, setPopupInfo] = useState<MarkerData | null>(null);

  const asOfById = useMemo(() => {
    const m = new Map<string, string>();
    occupancyRows?.forEach((r) => m.set(r.car_park_id, r.as_of));
    return m;
  }, [occupancyRows]);

  useEffect(() => {
    if (markers.length === 0 || !mapRef.current) return;
    const sig = markers.map((m) => m.id).slice().sort().join("|");
    if (sig === fittedSig.current) return;
    fittedSig.current = sig;

    const lngs = markers.map((m) => m.lon);
    const lats = markers.map((m) => m.lat);
    const bounds: LngLatBoundsLike = [
      [Math.min(...lngs) - 0.01, Math.min(...lats) - 0.01],
      [Math.max(...lngs) + 0.01, Math.max(...lats) + 0.01],
    ];
    mapRef.current.fitBounds(bounds, { padding: 60, maxZoom: 14, duration: 500 });
  }, [markers]);

  const handleMarkerClick = useCallback(
    (data: MarkerData) => {
      if (isDesktop) {
        setPopupInfo(data);
      }
      onSelectMarker(data.id);
    },
    [isDesktop, onSelectMarker]
  );

  return (
    <div className="relative h-full w-full bg-park-mist">
      <Map
        ref={mapRef}
        initialViewState={{
          ...DEFAULT_CENTER,
          zoom: DEFAULT_ZOOM,
        }}
        style={{ width: "100%", height: "100%" }}
        mapStyle={MAP_STYLE}
        attributionControl={false}
      >
        <NavigationControl position="bottom-right" showCompass={false} />

        {loading && !markers.length
          ? SKELETON_COORDS.map((pos, i) => (
              <CarParkMarker
                key={`skeleton-${i}`}
                data={{
                  id: `skeleton-${i}`,
                  name: "",
                  lat: pos[1],
                  lon: pos[0],
                  pct: 0,
                  source: "simulated",
                  mode: "live",
                  predictionPending: false,
                  predictionMissing: true,
                }}
                isSkeleton
                onClick={() => {}}
              />
            ))
          : null}

        {markers.map((data) => (
          <CarParkMarker
            key={data.id}
            data={data}
            onClick={() => handleMarkerClick(data)}
          />
        ))}

        {popupInfo && isDesktop && (
          <Popup
            longitude={popupInfo.lon}
            latitude={popupInfo.lat}
            anchor="bottom"
            onClose={() => setPopupInfo(null)}
            closeButton={true}
            closeOnClick={false}
            className="park-popup"
          >
            <div className="min-w-[220px] p-1">
              <CarParkDetail
                data={popupInfo}
                asOf={asOfById.get(popupInfo.id)}
                viewTime={viewTime}
                compact
              />
            </div>
          </Popup>
        )}
      </Map>

      {predictLoading && viewTime && isDesktop ? (
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
