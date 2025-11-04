from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable


@dataclass(frozen=True)
class AreaOfInterest:
    """Representa uma área de interesse a partir de um GeoJSON."""

    geometry: Dict

    @classmethod
    def from_geojson(cls, geojson_path: Path) -> "AreaOfInterest":
        with Path(geojson_path).open("r", encoding="utf-8") as file:
            geometry = json.load(file)
        return cls(geometry=geometry)

    def to_wkt(self) -> str:
        """Converte a geometria armazenada em representação WKT (polígono)."""
        geometry = self._extract_geometry(self.geometry)
        gtype = geometry.get("type")
        coordinates = geometry.get("coordinates")

        if gtype == "Polygon":
            return self._polygon_to_wkt(coordinates)
        if gtype == "MultiPolygon":
            polygon_wkts = [self._polygon_to_wkt(polygon) for polygon in coordinates]
            inner = ", ".join(wkt.replace("POLYGON ", "", 1) for wkt in polygon_wkts)
            return f"MULTIPOLYGON ({inner})"

        raise ValueError(f"Unsupported geometry type: {gtype}")

    @staticmethod
    def _extract_geometry(geometry: Dict) -> Dict:
        if geometry.get("type") == "FeatureCollection":
            features = geometry.get("features", [])
            if not features:
                raise ValueError("GeoJSON feature collection is empty.")
            return features[0]["geometry"]
        if geometry.get("type") == "Feature":
            return geometry["geometry"]
        return geometry

    @staticmethod
    def _polygon_to_wkt(coordinates: Iterable[Iterable[Iterable[float]]]) -> str:
        rings = []
        for ring in coordinates:
            if not ring:
                raise ValueError("GeoJSON polygon ring is empty.")
            if ring[0] != ring[-1]:
                ring = list(ring) + [ring[0]]
            rings.append(", ".join(f"{lon} {lat}" for lon, lat in ring))
        inner = ", ".join(f"({ring})" for ring in rings)
        return f"POLYGON ({inner})"
