import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { STATION, ARENA } from "../constants";

export default function MapView({ plan }) {
  const legs = plan.local_legs.map((l) => ({ ...l, pts: l.path ?? [STATION, ARENA] }));
  const bounds = [STATION, ARENA, ...legs.flatMap((l) => l.pts)];

  return (
    <MapContainer key={plan.id} bounds={bounds} boundsOptions={{ padding: [30, 30] }}
                  className="map" scrollWheelZoom={false}>
      <TileLayer
        attribution="&copy; OpenStreetMap contributors"
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />
      {legs.map((l, i) => (
        <Polyline
          key={i}
          positions={l.pts}
          pathOptions={
            l.mode === "walk"
              ? { color: "#555", weight: 4, dashArray: "6 8" }
              : { color: "#d33", weight: 6 }
          }
        >
          {l.mode !== "walk" && l.line && <Tooltip sticky>Line {l.line}</Tooltip>}
        </Polyline>
      ))}
      <CircleMarker center={STATION} radius={9} pathOptions={{ color: "#1a56db", fillOpacity: 1 }}>
        <Tooltip permanent direction="top">Kraków Główny</Tooltip>
      </CircleMarker>
      <CircleMarker center={ARENA} radius={9} pathOptions={{ color: "#2e9e4f", fillOpacity: 1 }}>
        <Tooltip permanent direction="top">Tauron Arena</Tooltip>
      </CircleMarker>
    </MapContainer>
  );
}
