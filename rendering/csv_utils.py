from __future__ import annotations

import csv
from pathlib import Path
from typing import Tuple

import numpy as np
from affine import Affine
from rasterio.transform import array_bounds


def load_csv_grid(path: Path) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Read CSV exported from the pipeline and return lon/lat/value arrays."""
    with path.open("r", encoding="utf-8") as file:
        reader = csv.DictReader(file)
        lons: list[float] = []
        lats: list[float] = []
        values: list[float] = []
        for row in reader:
            try:
                lon = float(row["longitude"])
                lat = float(row["latitude"])
                val = float(row["value"])
            except KeyError as exc:
                raise ValueError(f"CSV {path} precisa das colunas longitude, latitude, value.") from exc
            except ValueError as exc:
                raise ValueError(f"CSV {path} possui valores invalidos: {row}") from exc
            lons.append(lon)
            lats.append(lat)
            values.append(val)
    if not lons:
        raise ValueError(f"CSV {path} esta vazio ou sem dados validos.")
    return np.array(lons, dtype=np.float64), np.array(lats, dtype=np.float64), np.array(values, dtype=np.float32)


def build_grid(lons: np.ndarray, lats: np.ndarray, values: np.ndarray) -> Tuple[np.ndarray, Affine]:
    """Convert lon/lat/value vectors into a raster grid plus transform."""
    unique_lons = np.unique(lons)
    unique_lats = np.unique(lats)[::-1]
    if unique_lons.size * unique_lats.size != lons.size:
        raise ValueError("Os dados nao formam uma grade regular. Garanta que o CSV veio do exportador oficial.")

    lon_index = {lon: idx for idx, lon in enumerate(unique_lons)}
    lat_index = {lat: idx for idx, lat in enumerate(unique_lats)}

    grid = np.full((unique_lats.size, unique_lons.size), np.nan, dtype=np.float32)
    for lon, lat, val in zip(lons, lats, values, strict=False):
        grid[lat_index[lat], lon_index[lon]] = val

    lon_res = float(unique_lons[1] - unique_lons[0]) if unique_lons.size > 1 else 0.0001
    lat_res = float(unique_lats[0] - unique_lats[1]) if unique_lats.size > 1 else 0.0001
    lon_origin = float(unique_lons[0] - lon_res / 2)
    lat_origin = float(unique_lats[0] + lat_res / 2)
    transform = Affine.translation(lon_origin, lat_origin) * Affine.scale(lon_res, -lat_res)
    return grid, transform


def expand_to_clip_bounds(
    data: np.ndarray,
    transform: Affine,
    clip_bounds: Tuple[float, float, float, float],
) -> Tuple[np.ndarray, Affine]:
    """Pad the grid so that it matches the requested clip bounds."""
    lon_res = float(transform.a)
    lat_res = float(-transform.e)
    if lon_res <= 0 or lat_res <= 0:
        raise ValueError("Transformacao invalida ao reconstruir grade do CSV.")

    current_bounds = array_bounds(data.shape[0], data.shape[1], transform)

    def _pad_count(delta: float, resolution: float) -> int:
        pixels = delta / resolution
        if pixels <= 0:
            return 0
        return int(round(pixels))

    left_pad = _pad_count(current_bounds[0] - clip_bounds[0], lon_res)
    right_pad = _pad_count(clip_bounds[2] - current_bounds[2], lon_res)
    top_pad = _pad_count(clip_bounds[3] - current_bounds[3], lat_res)
    bottom_pad = _pad_count(current_bounds[1] - clip_bounds[1], lat_res)

    if any(value != 0 for value in (left_pad, right_pad, top_pad, bottom_pad)):
        padded_height = top_pad + data.shape[0] + bottom_pad
        padded_width = left_pad + data.shape[1] + right_pad
        padded = np.full((padded_height, padded_width), np.nan, dtype=data.dtype)
        padded[top_pad : top_pad + data.shape[0], left_pad : left_pad + data.shape[1]] = data
        data = padded
        lon_origin = clip_bounds[0] - lon_res / 2.0
        lat_origin = clip_bounds[3] + lat_res / 2.0
        transform = Affine.translation(lon_origin, lat_origin) * Affine.scale(lon_res, -lat_res)

    return data, transform
