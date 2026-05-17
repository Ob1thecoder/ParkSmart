import { useMemo } from "react";
import { Marker, Popup } from "react-leaflet";
import type { MarkerData } from "../../types";
import { createParkDivIcon } from "./markerIcon";
import { CarParkDetail } from "./CarParkDetail";

type Props = {
  data: MarkerData;
  isDesktop: boolean;
  asOf?: string;
  viewTime: Date | null;
  onSelect: (id: string) => void;
};

export function CarParkMarker({ data, isDesktop, asOf, viewTime, onSelect }: Props) {
  // Rebuild the icon only when something it draws actually changes.
  const icon = useMemo(
    () => createParkDivIcon(data),
    [data.pct, data.source, data.predictionMissing, data.predictionPending],
  );

  return (
    <Marker
      position={[data.lat, data.lon]}
      icon={icon}
      eventHandlers={{ click: () => onSelect(data.id) }}
    >
      {/* Desktop shows the detail in a Leaflet popup (Leaflet handles
          open/close on marker click). Mobile routes it to the bottom sheet. */}
      {isDesktop ? (
        <Popup>
          <div className="min-w-[220px]">
            <CarParkDetail data={data} asOf={asOf} viewTime={viewTime} compact />
          </div>
        </Popup>
      ) : null}
    </Marker>
  );
}
