"use client";

import { CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import type { ArticleSummary } from "@/lib/types";

export function IndiaMap({ articles }: { articles: ArticleSummary[] }) {
  const located = articles.filter((article) => article.latitude !== undefined && article.longitude !== undefined);
  return <MapContainer center={[22.8, 79]} zoom={4} minZoom={4} scrollWheelZoom={false} className="h-full min-h-[520px] w-full" maxBounds={[[5, 65], [38, 100]]}><TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />{located.map((article) => <CircleMarker key={`${article.article_id}-${article.food_keyword}`} center={[article.latitude!, article.longitude!]} radius={7} pathOptions={{ color: "#761c2f", fillColor: "#c27b24", fillOpacity: .75 }}><Popup><strong>{article.title}</strong><br />{article.location_state ?? "State unavailable"}</Popup></CircleMarker>)}</MapContainer>;
}
