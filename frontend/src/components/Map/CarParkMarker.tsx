import { useMemo } from "react";
import { Marker, Popup } from "react-leaflet";
import type { MarkerData } from "../../types";
import { createParkDivIcon } from "./markerIcon";
import { CarParkDetail } from "./CarParkDetail";

type Props = {
  data: MarkerData;
  isDesktop: boolean;
  asOf?: string;
  onSelect: (id: string) => void;
};

export function CarParkMarker({ data, isDesktop, asOf, onSelect }: Props) {
  // Rebuild the icon only when something it draws actually changes.
  const icon = useMemo(
    () => createParkDivIcon(data),
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [data.pct, data.source, data.predictionMissing],
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
            <CarParkDetail data={data} asOf={asOf} compact />
          </div>
        </Popup>
      ) : null}
    </Marker>
  );
}
