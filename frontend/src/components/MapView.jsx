import { MapContainer, TileLayer, Polyline, CircleMarker, Tooltip } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import { STATION, ARENA } from "../constants";

// Leaflet draws on a canvas/SVG that CSS variables do not reach, so the colours are literal.
const TRAM = "#1f4fe0";
const WALK = "#64748b";

export default function MapView({ plan }) {
  const legs = plan.local_legs.map((l) => ({ ...l, pts: l.path ?? [STATION, ARENA] }));
  const bounds = [STATION, ARENA, ...legs.flatMap((l) => l.pts)];

  return (
    <div className="panel">
      <h3>From the station to the entrance</h3>
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
                ? { color: WALK, weight: 5, dashArray: "2 9", lineCap: "round" }
                : { color: TRAM, weight: 7, opacity: 0.9 }
            }
          >
            {l.mode !== "walk" && l.line && <Tooltip sticky>Line {l.line}</Tooltip>}
          </Polyline>
        ))}
        <CircleMarker center={STATION} radius={10}
                      pathOptions={{ color: "#fff", weight: 3, fillColor: TRAM, fillOpacity: 1 }}>
          <Tooltip permanent direction="top">Kraków Główny</Tooltip>
        </CircleMarker>
        <CircleMarker center={ARENA} radius={10}
                      pathOptions={{ color: "#fff", weight: 3, fillColor: "#12803d", fillOpacity: 1 }}>
          <Tooltip permanent direction="top">Tauron Arena</Tooltip>
        </CircleMarker>
      </MapContainer>
      <div className="map-legend">
        <span><i className="tram" />Tram</span>
        <span><i className="walk" />Walking</span>
      </div>
    </div>
  );
}
