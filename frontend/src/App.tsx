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
    <div className="flex h-dvh flex-col">
      <header className="flex shrink-0 items-center justify-between bg-park-ink px-4 py-3 z-[500]">
        <h1 className="font-display text-base font-semibold text-white tracking-wide">ParkChatswood</h1>
        <span className="text-xs font-medium uppercase tracking-widest text-park-fern">Chatswood</span>
      </header>

      <div className="flex flex-1 flex-col md:flex-row overflow-hidden">
        <div className="relative flex flex-1 flex-col min-h-[50vh] md:min-h-0">
          <MapView
            markers={markers}
            occupancyRows={data}
            loading={!data && !loadError}
            loadError={loadError}
            onRetry={retry}
            isDesktop={isDesktop}
            viewTime={viewTime}
            predictLoading={predictLoading}
            onSelectMarker={handleSelectMarker}
          />

          <div className="pointer-events-none absolute left-0 right-0 top-0 z-[400] p-3 md:left-4 md:right-auto md:max-w-md">
            <div className="pointer-events-auto space-y-0">
              <SearchField onStreetChosen={(s) => void zones.load(s)} onClear={zones.clear} />
              <ZoneRulesCard
                zone={zones.zone}
                notFound={zones.notFound}
                loadError={zones.loadError}
                loading={zones.loading}
                streetQuery={zones.streetQuery}
                onClose={zones.clear}
              />
              {stale ? (
                <p className="mt-2 rounded-lg bg-amber-50/95 px-2 py-1 text-[11px] text-amber-900 shadow-sm">
                  Live data may be stale — reconnecting in the background.
                </p>
              ) : null}
            </div>
          </div>

          <div className="pointer-events-none absolute bottom-4 left-0 right-0 z-[400] flex flex-col items-center gap-3 px-3 md:bottom-6 md:left-4 md:right-auto md:items-start">
            {!isDesktop && !sheetOpen ? (
              <button
                type="button"
                onClick={() => setSheetOpen(true)}
                className="pointer-events-auto flex items-center gap-2 rounded-full bg-park-ink px-5 py-3 text-sm font-semibold text-white shadow-lg"
              >
                <span className="flex h-5 w-5 items-center justify-center rounded-full bg-white/20 text-[10px] font-bold">V</span>
                Ask Valet…
              </button>
            ) : null}
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
          detailViewTime={viewTime}
          onCloseDetail={() => setSelectedId(null)}
          occupancy={data ?? []}
          occupancyLoading={!data && !loadError}
          predictions={byId}
          viewTime={viewTime ?? undefined}
          onSelectCarPark={handleSelectMarker}
        />
      </div>
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
