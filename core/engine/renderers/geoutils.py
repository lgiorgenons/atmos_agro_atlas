from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Iterable, Optional, Tuple
import json


def load_geojson(path: Path) -> Dict[str, Any]:
    """Read a GeoJSON file and return its geometry dict."""
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def iterate_geometries(geometry: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    """Yield Polygon geometries from a GeoJSON structure."""
    gtype = geometry.get("type")
    if gtype == "FeatureCollection":
        for feature in geometry.get("features", []):
            yield from iterate_geometries(feature)
    elif gtype == "Feature":
        yield from iterate_geometries(geometry["geometry"])
    elif gtype == "Polygon":
        yield geometry
    elif gtype == "MultiPolygon":
        for polygon in geometry.get("coordinates", []):
            yield {"type": "Polygon", "coordinates": polygon}


def extract_geometry_bounds(geojson_data: Dict[str, Any]) -> Optional[Tuple[float, float, float, float]]:
    """Return a bounding box (min_lon, min_lat, max_lon, max_lat) for the GeoJSON."""

    def extract_geometry(geometry: Dict[str, Any]) -> Dict[str, Any]:
        if geometry.get("type") == "FeatureCollection":
            features = geometry.get("features", [])
            if not features:
                raise ValueError("GeoJSON sem features.")
            return extract_geometry(features[0])
        if geometry.get("type") == "Feature":
            return extract_geometry(geometry["geometry"])
        return geometry

    geometry = extract_geometry(geojson_data)
    coords = geometry.get("coordinates")
    gtype = geometry.get("type")

    if gtype == "Polygon":
        points = coords[0]
    elif gtype == "MultiPolygon":
        points = [pt for polygon in coords for pt in polygon[0]]
    else:
        return None

    lons = [pt[0] for pt in points]
    lats = [pt[1] for pt in points]
    return min(lons), min(lats), max(lons), max(lats)

