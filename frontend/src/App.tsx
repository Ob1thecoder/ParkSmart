import { useCallback, useEffect, useMemo, useState } from "react";
import { ChatProvider } from "./context/ChatContext";
import { useOccupancy } from "./hooks/useOccupancy";
import { usePredictions } from "./hooks/usePredictions";
import { useZones } from "./hooks/useZones";
import { useMediaQuery } from "./hooks/useMediaQuery";
import { buildMarkerDataList } from "./lib/buildMarkers";
import { MapView } from "./components/Map/MapView";
import { TimeScrubber } from "./components/Scrubber/TimeScrubber";
import { SearchField } from "./components/Zones/SearchField";
import { ZoneRulesCard } from "./components/Zones/ZoneRulesCard";
import { AssistantPanel } from "./components/Assistant/AssistantPanel";

function Shell() {
  const isDesktop = useMediaQuery("(min-width: 768px)");
  const [viewTime, setViewTime] = useState<Date | null>(null);
  const [sheetOpen, setSheetOpen] = useState(false);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data, stale, loadError, retry } = useOccupancy();
  const { byId, loading: predictLoading } = usePredictions(viewTime, data);

  const markers = useMemo(
    () => buildMarkerDataList(data, viewTime, byId, predictLoading),
    [data, viewTime, byId, predictLoading],
  );

  const zones = useZones();

  const handleSelectMarker = useCallback(
    (id: string) => setSelectedId((cur) => (cur === id ? null : id)),
    [],
  );

  const detail = useMemo(() => {
    if (isDesktop) return null;
    return markers.find((m) => m.id === selectedId) ?? null;
  }, [markers, selectedId, isDesktop]);

  const detailAsOf = useMemo(
    () => data?.find((r) => r.car_park_id === selectedId)?.as_of,
    [data, selectedId],
  );

  useEffect(() => {
    if (selectedId && !isDesktop) setSheetOpen(true);
  }, [selectedId, isDesktop]);

  return (
    <div className="flex h-dvh flex-col md:flex-row">
      <div className="relative min-h-[56vh] flex-1 md:min-h-0">
        <MapView
          markers={markers}
          occupancyRows={data}
          loading={!data && !loadError}
          loadError={loadError}
          onRetry={retry}
          isDesktop={isDesktop}
          onSelectMarker={handleSelectMarker}
        />

        <div className="pointer-events-none absolute left-0 right-0 top-0 z-[400] p-3 md:left-4 md:right-auto md:max-w-md">
          <div className="pointer-events-auto space-y-0">
            <SearchField onStreetChosen={(s) => void zones.load(s)} />
            <ZoneRulesCard
              zone={zones.zone}
              notFound={zones.notFound}
              loadError={zones.loadError}
              loading={zones.loading}
              streetQuery={zones.streetQuery}
            />
            {stale ? (
              <p className="mt-2 rounded-lg bg-amber-50/95 px-2 py-1 text-[11px] text-amber-900 shadow-sm">
                Live data may be stale — reconnecting in the background.
              </p>
            ) : null}
          </div>
        </div>

        <div className="pointer-events-none absolute bottom-28 left-0 right-0 z-[400] flex justify-center px-3 md:bottom-6 md:left-4 md:right-auto md:justify-start">
          <div className="pointer-events-auto w-full max-w-md">
            <TimeScrubber
              viewTime={viewTime}
              onViewTimeChange={setViewTime}
              predictLoading={predictLoading}
            />
          </div>
        </div>
      </div>

      <AssistantPanel
        isDesktop={isDesktop}
        mobileExpanded={sheetOpen}
        onMobileExpandedChange={setSheetOpen}
        detail={detail}
        detailAsOf={detailAsOf}
        onCloseDetail={() => setSelectedId(null)}
      />
    </div>
  );
}

export default function App() {
  return (
    <ChatProvider>
      <Shell />
    </ChatProvider>
  );
}
