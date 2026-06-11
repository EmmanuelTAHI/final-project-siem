"use client";

import { useEffect, useRef } from "react";
import type { GeoData } from "@/types";

// Mapping ISO2 → coordonnées approximatives
const GEO_COORDS: Record<string, [number, number]> = {
  FR: [46.2276, 2.2137], US: [37.0902, -95.7129], GB: [55.3781, -3.436],
  DE: [51.1657, 10.4515], CN: [35.8617, 104.1954], RU: [61.5240, 105.3188],
  IN: [20.5937, 78.9629], BR: [14.2350, -51.9253], JP: [36.2048, 138.2529],
  KR: [35.9078, 127.7669], AU: [25.2744, 133.7751], CA: [56.1304, -106.3468],
  NL: [52.1326, 5.2913], IT: [41.8719, 12.5674], ES: [40.4637, -3.7492],
  SE: [60.1282, 18.6435], NO: [60.4720, 8.4689], CH: [46.8182, 8.2275],
  PL: [51.9194, 19.1451], UA: [48.3794, 31.1656], NG: [9.0820, 8.6753],
  ZA: [30.5595, 22.9375], EG: [26.8206, 30.8025], TH: [15.8700, 100.9925],
  SG: [1.3521, 103.8198], ID: [0.7893, 113.9213], MY: [4.2105, 101.9758],
  MX: [23.6345, -102.5528], AR: [38.4161, -63.6167], TR: [38.9637, 35.2433],
  SA: [23.8859, 45.0792], AE: [23.4241, 53.8478], IL: [31.0461, 34.8516],
  PK: [30.3753, 69.3451], BD: [23.6850, 90.3563], IR: [32.4279, 53.6880],
  IQ: [33.2232, 43.6793], VN: [14.0583, 108.2772], PH: [12.8797, 121.7740],
};

interface GeoMapLeafletProps {
  data: GeoData[];
  height?: string;
}

export function GeoMapLeaflet({ data, height = "400px" }: GeoMapLeafletProps) {
  const mapRef = useRef<HTMLDivElement>(null);
  const mapInstanceRef = useRef<unknown>(null);

  useEffect(() => {
    if (typeof window === "undefined" || !mapRef.current) return;
    if (mapInstanceRef.current) return;

    import("leaflet").then((L) => {
      // Fix icône Leaflet en Next.js
      // @ts-ignore
      delete L.Icon.Default.prototype._getIconUrl;
      L.Icon.Default.mergeOptions({
        iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
        iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
        shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
      });

      // React StrictMode monte/démonte l'effet deux fois en dev : Leaflet laisse
      // un _leaflet_id sur le conteneur, ce qui fait échouer la ré-initialisation.
      // @ts-ignore
      if (mapRef.current && mapRef.current._leaflet_id) {
        // @ts-ignore
        delete mapRef.current._leaflet_id;
      }

      const map = L.map(mapRef.current!, {
        center: [20, 0],
        zoom: 2,
        zoomControl: true,
        scrollWheelZoom: false,
        attributionControl: false,
      });

      L.tileLayer("https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png", {
        attribution: "© CartoDB",
        subdomains: "abcd",
        maxZoom: 19,
      }).addTo(map);

      const maxCount = Math.max(...data.map((d) => d.count), 1);

      data.forEach((point) => {
        const coords = GEO_COORDS[point.country_code ?? point.country];
        if (!coords) return;

        const radius = Math.max(6, Math.min(30, (point.count / maxCount) * 30));
        const isThreat = point.threat_count > 0;
        const color = isThreat ? "#ef4444" : "#3b82f6";
        const opacity = isThreat ? 0.8 : 0.5;

        const circle = L.circleMarker(coords, {
          radius,
          fillColor: color,
          color: color,
          weight: 1,
          opacity: 1,
          fillOpacity: opacity,
        }).addTo(map);

        const code = (point.country_code ?? "").toLowerCase();
        const flagImg = code.length === 2
          ? `<img src="https://flagcdn.com/w40/${code}.png" width="20" height="15" style="border-radius:2px;vertical-align:middle;margin-right:6px;box-shadow:0 0 0 1px rgba(255,255,255,0.15)" />`
          : "";
        circle.bindPopup(`
          <div style="font-family:system-ui,monospace;font-size:12px;min-width:170px;line-height:1.6">
            <div style="font-size:14px;font-weight:700;margin-bottom:6px;display:flex;align-items:center">
              ${flagImg}<span>${point.country}</span>
            </div>
            <div style="color:#94a3b8;font-size:10px;margin-bottom:8px;letter-spacing:.05em">${(point.country_code ?? "").toUpperCase()}</div>
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
              <span style="color:#94a3b8">Logs</span>
              <b>${point.count.toLocaleString()}</b>
            </div>
            <div style="display:flex;justify-content:space-between;margin-bottom:2px">
              <span style="color:#94a3b8">Part</span>
              <span>${point.percentage?.toFixed(1) ?? 0}%</span>
            </div>
            ${isThreat ? `<div style="display:flex;justify-content:space-between;margin-top:6px;padding-top:6px;border-top:1px solid #334155"><span style="color:#ef4444">⚠ Menaces</span><b style="color:#ef4444">${point.threat_count}</b></div>` : ""}
          </div>
        `, { className: "logplus-popup" });
      });

      mapInstanceRef.current = map;
    });

    return () => {
      if (mapInstanceRef.current) {
        // @ts-ignore
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, []);

  useEffect(() => {
    if (!mapInstanceRef.current || !data.length) return;
    import("leaflet").then((L) => {
      const map = mapInstanceRef.current as unknown as ReturnType<typeof L.map>;
      // @ts-ignore
      map.eachLayer((layer: unknown) => {
        // @ts-ignore
        if (layer instanceof L.CircleMarker) map.removeLayer(layer);
      });

      const maxCount = Math.max(...data.map((d) => d.count), 1);
      data.forEach((point) => {
        const coords = GEO_COORDS[point.country_code ?? point.country];
        if (!coords) return;
        const radius = Math.max(6, Math.min(30, (point.count / maxCount) * 30));
        const isThreat = point.threat_count > 0;
        const color = isThreat ? "#ef4444" : "#3b82f6";
        const circle = L.circleMarker(coords, {
          radius, fillColor: color, color, weight: 1, opacity: 1, fillOpacity: isThreat ? 0.8 : 0.5,
        }).addTo(map);
        const code2 = (point.country_code ?? "").toLowerCase();
        const flagImg2 = code2.length === 2
          ? `<img src="https://flagcdn.com/w40/${code2}.png" width="20" height="15" style="border-radius:2px;vertical-align:middle;margin-right:6px;box-shadow:0 0 0 1px rgba(255,255,255,0.15)" />`
          : "";
        circle.bindPopup(`<div style="font-family:system-ui,monospace;font-size:12px;min-width:150px"><div style="font-size:13px;font-weight:700;margin-bottom:4px;display:flex;align-items:center">${flagImg2}${point.country}</div><div style="display:flex;justify-content:space-between"><span style="color:#94a3b8">Logs</span><b>${point.count.toLocaleString()}</b></div>${isThreat ? `<div style="margin-top:4px;padding-top:4px;border-top:1px solid #334155;display:flex;justify-content:space-between"><span style="color:#ef4444">⚠ Menaces</span><b style="color:#ef4444">${point.threat_count}</b></div>` : ""}</div>`);
      });
    });
  }, [data]);

  return (
    <>
      <link
        rel="stylesheet"
        href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"
      />
      <style>{`
        .leaflet-container { background: #0f172a !important; border-radius: 0.5rem; }
        .logplus-popup .leaflet-popup-content-wrapper { background: #1e293b; color: #f1f5f9; border: 1px solid #334155; }
        .logplus-popup .leaflet-popup-tip { background: #1e293b; }
      `}</style>
      <div ref={mapRef} style={{ height, width: "100%", borderRadius: "0.5rem" }} />
    </>
  );
}
