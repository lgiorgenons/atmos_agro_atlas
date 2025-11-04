from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import folium
import numpy as np
from branca.colormap import LinearColormap

from .csv_utils import build_grid, expand_to_clip_bounds, load_csv_grid
from .geoutils import extract_geometry_bounds, load_geojson
from .index_map import IndexMapData, IndexMapOptions, IndexMapRenderer
from .raster import apply_smoothing, apply_unsharp_mask, upsample_raster


@dataclass
class CSVMapOptions:
    colormap: str = "RdYlGn"
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    opacity: float = 0.75
    tiles: str = "CartoDB positron"
    tile_attr: Optional[str] = None
    padding_factor: float = 0.3
    clip: bool = False
    upsample: float = 1.0
    sharpen: bool = False
    sharpen_radius: float = 1.0
    sharpen_amount: float = 1.3
    smooth_radius: float = 0.0


class CSVMapRenderer:
    """Object-oriented renderer for CSV-derived grids."""

    def __init__(self, options: Optional[CSVMapOptions] = None):
        self.options = options or CSVMapOptions()

    def prepare(
        self,
        csv_path: Path,
        overlays: Optional[Iterable[Path]] = None,
    ) -> IndexMapData:
        lons, lats, values = load_csv_grid(csv_path)
        grid, transform = build_grid(lons, lats, values)

        overlays = overlays or []
        overlay_geojsons = [load_geojson(path) for path in overlays]
        clip_bounds = self._compute_clip_bounds(overlay_geojsons) if self.options.clip else None

        data = grid
        if self.options.sharpen:
            data = apply_unsharp_mask(data, self.options.sharpen_radius, self.options.sharpen_amount)

        if overlay_geojsons and self.options.clip:
            data = IndexMapRenderer._mask_with_geojson(data, transform, overlay_geojsons)  # type: ignore[attr-defined]

        if clip_bounds is not None and self.options.clip:
            data, transform = expand_to_clip_bounds(data, transform, clip_bounds)

        data, transform = upsample_raster(data, transform, self.options.upsample)
        data = apply_smoothing(data, self.options.smooth_radius)

        if overlay_geojsons and self.options.clip and self.options.upsample > 1.0:
            data = IndexMapRenderer._mask_with_geojson(data, transform, overlay_geojsons)  # type: ignore[attr-defined]

        bounds = self._array_bounds(data, transform)

        return IndexMapData(
            data=data,
            transform=transform,
            bounds=bounds,
            clip_bounds=clip_bounds,
            overlays=overlay_geojsons,
            index_name=csv_path.stem,
        )

    def render_html(self, prepared: IndexMapData, output_path: Path) -> Path:
        renderer = IndexMapRenderer(
            IndexMapOptions(
                cmap_name=self.options.colormap,
                vmin=self.options.vmin,
                vmax=self.options.vmax,
                opacity=self.options.opacity,
                tiles=self.options.tiles,
                tile_attr=self.options.tile_attr,
                clip=prepared.clip_bounds is not None,
            )
        )
        return renderer.render_html(prepared, output_path)

    def _compute_clip_bounds(
        self,
        overlay_geojsons: Sequence[Dict],
    ) -> Optional[Tuple[float, float, float, float]]:
        geom_bounds = [extract_geometry_bounds(data) for data in overlay_geojsons]
        geom_bounds = [bounds for bounds in geom_bounds if bounds is not None]
        if not geom_bounds:
            return None
        min_lon_geo = min(b[0] for b in geom_bounds)
        min_lat_geo = min(b[1] for b in geom_bounds)
        max_lon_geo = max(b[2] for b in geom_bounds)
        max_lat_geo = max(b[3] for b in geom_bounds)
        width_geo = max_lon_geo - min_lon_geo
        height_geo = max_lat_geo - min_lat_geo
        pad_lon = width_geo * self.options.padding_factor / 2
        pad_lat = height_geo * self.options.padding_factor / 2
        return (
            min_lon_geo - pad_lon,
            min_lat_geo - pad_lat,
            max_lon_geo + pad_lon,
            max_lat_geo + pad_lat,
        )

    @staticmethod
    def _array_bounds(data: np.ndarray, transform) -> Tuple[float, float, float, float]:
        from rasterio.transform import array_bounds

        return array_bounds(data.shape[0], data.shape[1], transform)


def build_csv_map(
    csv_path: Path,
    output_path: Path,
    colormap: str = "RdYlGn",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    opacity: float = 0.75,
    overlays: Optional[Iterable[Path]] = None,
    tiles: str = "CartoDB positron",
    tile_attr: Optional[str] = None,
    padding_factor: float = 0.3,
    clip: bool = False,
    sharpen: bool = False,
    sharpen_radius: float = 1.0,
    sharpen_amount: float = 1.3,
    upsample: float = 1.0,
    smooth_radius: float = 0.0,
) -> Path:
    renderer = CSVMapRenderer(
        CSVMapOptions(
            colormap=colormap,
            vmin=vmin,
            vmax=vmax,
            opacity=opacity,
            tiles=tiles,
            tile_attr=tile_attr,
            padding_factor=padding_factor,
            clip=clip,
            upsample=upsample,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
            smooth_radius=smooth_radius,
        )
    )
    prepared = renderer.prepare(csv_path=csv_path, overlays=overlays)
    return renderer.render_html(prepared, output_path)
