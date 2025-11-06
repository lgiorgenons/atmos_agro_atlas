from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import folium
import numpy as np
from affine import Affine
from branca.colormap import LinearColormap
from matplotlib import colormaps, colors
from rasterio.features import rasterize
from rasterio.transform import array_bounds

from core.engine.exporters import CSVExporter

from .geoutils import extract_geometry_bounds, iterate_geometries, load_geojson
from .raster import apply_smoothing, apply_unsharp_mask, generate_rgba, load_raster, upsample_raster
from .options import BaseMapOptions


@dataclass
class IndexMapOptions(BaseMapOptions):
    cmap_name: str = "RdYlGn"
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    opacity: float = 0.75

@dataclass
class IndexMapData:
    data: np.ndarray
    transform: Affine
    bounds: Tuple[float, float, float, float]
    clip_bounds: Optional[Tuple[float, float, float, float]]
    overlays: List[Dict[str, Any]]
    index_name: str

class IndexMapRenderer:
    """Renderer orientado a objetos para mapas de um unico indice."""

    def __init__(
        self,
        options: Optional[IndexMapOptions] = None,
        *,
        csv_exporter: Optional[CSVExporter] = None,
    ):
        self.options = options or IndexMapOptions()
        self._csv_exporter = csv_exporter or CSVExporter()

    def prepare(
        self,
        index_path: Path,
        overlays: Optional[Iterable[Path]] = None,
    ) -> IndexMapData:
        overlay_geojsons = [load_geojson(path) for path in (overlays or [])]
        clip_bounds = self._compute_clip_bounds(overlay_geojsons) if self.options.clip else None

        data, transform, _ = load_raster(index_path, clip_bounds_wgs84=clip_bounds)

        if self.options.sharpen:
            data = apply_unsharp_mask(data, self.options.sharpen_radius, self.options.sharpen_amount)

        if overlay_geojsons and self.options.clip:
            data = self._mask_with_geojson(data, transform, overlay_geojsons)

        data, transform = upsample_raster(data, transform, self.options.upsample)
        data = apply_smoothing(data, self.options.smooth_radius)

        if overlay_geojsons and self.options.clip and self.options.upsample > 1.0:
            data = self._mask_with_geojson(data, transform, overlay_geojsons)

        bounds = array_bounds(data.shape[0], data.shape[1], transform)

        return IndexMapData(
            data=data,
            transform=transform,
            bounds=bounds,
            clip_bounds=clip_bounds,
            overlays=overlay_geojsons,
            index_name=index_path.stem,
        )

    def render_html(self, prepared: IndexMapData, output_path: Path) -> Path:
        image, min_value, max_value = generate_rgba(
            prepared.data,
            self.options.cmap_name,
            self.options.vmin,
            self.options.vmax,
            self.options.opacity,
        )

        min_lon, min_lat, max_lon, max_lat = prepared.bounds
        if prepared.clip_bounds is not None:
            min_lon, min_lat, max_lon, max_lat = prepared.clip_bounds

        centre_lat = (min_lat + max_lat) / 2
        centre_lon = (min_lon + max_lon) / 2

        base_map = self._build_base_map(centre_lat, centre_lon)
        folium.raster_layers.ImageOverlay(
            image=image,
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            opacity=1.0,
            name=prepared.index_name,
        ).add_to(base_map)

        linear = LinearColormap(
            [colors.rgb2hex(colormaps[self.options.cmap_name](x)) for x in np.linspace(0, 1, 10)],
            vmin=min_value,
            vmax=max_value,
        )
        linear.caption = f"{prepared.index_name} (min={min_value:.3f}, max={max_value:.3f})"
        linear.add_to(base_map)

        for geojson_data in prepared.overlays:
            folium.GeoJson(data=geojson_data, name="AOI", style_function=lambda _: {"fillOpacity": 0}).add_to(base_map)

        folium.LayerControl().add_to(base_map)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        base_map.save(str(output_path))
        return output_path

    def export_csv(self, prepared: IndexMapData, output_path: Path) -> Path:
        data = prepared.data
        transform = prepared.transform

        return self._csv_exporter.export(data, transform, output_path)

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
        width = max_lon_geo - min_lon_geo
        height = max_lat_geo - min_lat_geo
        pad_lon = width * self.options.padding_factor / 2
        pad_lat = height * self.options.padding_factor / 2
        return (
            min_lon_geo - pad_lon,
            min_lat_geo - pad_lat,
            max_lon_geo + pad_lon,
            max_lat_geo + pad_lat,
        )

    def _build_base_map(self, centre_lat: float, centre_lon: float) -> folium.Map:
        base_map = folium.Map(
            location=[centre_lat, centre_lon],
            zoom_start=self.options.zoom_start,
            min_zoom=self.options.min_zoom,
            max_zoom=self.options.max_zoom,
            tiles=None,
        )
        native_limit = (
            self.options.max_native_zoom if not self.options.allow_basemap_stretch else self.options.max_zoom
        )
        if self.options.tiles.lower() != "none":
            folium.TileLayer(
                tiles=self.options.tiles,
                attr=self.options.tile_attr,
                name=self.options.tiles,
                overlay=False,
                control=True,
                min_zoom=self.options.min_zoom,
                max_zoom=self.options.max_zoom,
                max_native_zoom=native_limit,
            ).add_to(base_map)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Esri World Imagery",
            overlay=False,
            control=True,
            min_zoom=self.options.min_zoom,
            max_zoom=self.options.max_zoom,
            max_native_zoom=native_limit,
        ).add_to(base_map)
        return base_map

    @staticmethod
    def _mask_with_geojson(
        data: np.ndarray,
        transform: Affine,
        overlay_geojsons: Sequence[Dict],
    ) -> np.ndarray:
        shapes = []
        for geojson_data in overlay_geojsons:
            for geom in iterate_geometries(geojson_data):
                shapes.append((geom, 1))
        if not shapes:
            return data
        mask = rasterize(
            shapes=shapes,
            out_shape=data.shape,
            transform=transform,
            fill=0,
            all_touched=False,
            dtype=np.uint8,
        )
        return np.where(mask == 1, data, np.nan)


# Compatibilidade procedural -------------------------------------------------


def prepare_map_data(
    index_path: Path,
    overlays: Optional[Iterable[Path]],
    padding_factor: float,
    clip: bool,
    upsample: float,
    sharpen: bool,
    sharpen_radius: float,
    sharpen_amount: float,
    smooth_radius: float,
) -> IndexMapData:
    renderer = IndexMapRenderer(
        IndexMapOptions(
            padding_factor=padding_factor,
            clip=clip,
            upsample=upsample,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
            smooth_radius=smooth_radius,
        )
    )
    return renderer.prepare(index_path=index_path, overlays=overlays)


def build_map(
    prepared: IndexMapData,
    output_path: Path,
    cmap_name: str = "RdYlGn",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    opacity: float = 0.75,
    tiles: str = "CartoDB positron",
    tile_attr: Optional[str] = None,
) -> Path:
    renderer = IndexMapRenderer(
        IndexMapOptions(
            cmap_name=cmap_name,
            vmin=vmin,
            vmax=vmax,
            opacity=opacity,
            tiles=tiles,
            tile_attr=tile_attr,
            clip=prepared.clip_bounds is not None,
        )
    )
    return renderer.render_html(prepared, output_path)


def export_csv(prepared: IndexMapData, output_path: Path) -> Path:
    renderer = IndexMapRenderer()
    return renderer.export_csv(prepared, output_path)


# Alias de compatibilidade com scripts existentes
PreparedRaster = IndexMapData
