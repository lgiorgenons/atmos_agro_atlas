from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import folium
import numpy as np
from branca.colormap import LinearColormap
from matplotlib import colormaps, colors
from rasterio import Affine
from rasterio.features import rasterize

from .geoutils import extract_geometry_bounds, iterate_geometries, load_geojson
from .options import BaseMapOptions
from .raster import apply_smoothing, apply_unsharp_mask, generate_rgba, load_raster, upsample_raster


@dataclass
class MultiIndexMapOptions(BaseMapOptions):
    cmap_name: str = "RdYlGn"
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    opacity: float = 0.75


class MultiIndexMapRenderer:
    """Object-oriented renderer for multi-layer index maps."""

    def __init__(self, options: Optional[MultiIndexMapOptions] = None):
        self.options = options or MultiIndexMapOptions()

    def render(
        self,
        index_paths: Sequence[Path],
        output_path: Path,
        overlays: Optional[Iterable[Path]] = None,
    ) -> Path:
        """Render one HTML document with multiple index overlays."""

        if not index_paths:
            raise ValueError("At least one index GeoTIFF is required.")

        overlays = list(overlays or [])
        overlay_geojsons: List[Dict] = [load_geojson(path) for path in overlays]

        clip_bounds = self._compute_clip_bounds(overlay_geojsons) if self.options.clip else None

        first_data, first_transform, first_bounds = load_raster(index_paths[0], clip_bounds_wgs84=clip_bounds)
        if self.options.sharpen:
            first_data = apply_unsharp_mask(first_data, self.options.sharpen_radius, self.options.sharpen_amount)
        first_data, first_transform = upsample_raster(first_data, first_transform, self.options.upsample)
        first_data = apply_smoothing(first_data, self.options.smooth_radius)

        min_lon, min_lat, max_lon, max_lat = first_bounds
        if clip_bounds is not None:
            min_lon, min_lat, max_lon, max_lat = clip_bounds
        centre_lat = (min_lat + max_lat) / 2
        centre_lon = (min_lon + max_lon) / 2

        base_map = self._build_base_map(centre_lat, centre_lon)

        for position, idx_path in enumerate(index_paths):
            data, transform, bounds = load_raster(idx_path, clip_bounds_wgs84=clip_bounds)
            if self.options.sharpen:
                data = apply_unsharp_mask(data, self.options.sharpen_radius, self.options.sharpen_amount)
            if self.options.clip:
                data = self._mask_with_geojson(data, transform, overlay_geojsons)
            data, transform = upsample_raster(data, transform, self.options.upsample)
            data = apply_smoothing(data, self.options.smooth_radius)
            if self.options.clip and self.options.upsample > 1.0:
                data = self._mask_with_geojson(data, transform, overlay_geojsons)

            image, min_value, max_value = generate_rgba(
                data,
                self.options.cmap_name,
                self.options.vmin,
                self.options.vmax,
                self.options.opacity,
            )

            o_min_lon, o_min_lat, o_max_lon, o_max_lat = bounds
            if clip_bounds is not None:
                o_min_lon, o_min_lat, o_max_lon, o_max_lat = clip_bounds

            feature = folium.FeatureGroup(
                name=f"{Path(idx_path).stem} ({min_value:.2f}..{max_value:.2f})",
                show=(position == 0),
            )
            folium.raster_layers.ImageOverlay(
                image=image,
                bounds=[[o_min_lat, o_min_lon], [o_max_lat, o_max_lon]],
                opacity=1.0,
            ).add_to(feature)
            feature.add_to(base_map)

        for geojson_data in overlay_geojsons:
            folium.GeoJson(data=geojson_data, name="AOI", style_function=lambda _: {"fillOpacity": 0}).add_to(base_map)

        linear = LinearColormap(
            [colors.rgb2hex(colormaps[self.options.cmap_name](x)) for x in np.linspace(0, 1, 10)],
            vmin=0,
            vmax=1,
        )
        linear.caption = f"{self.options.cmap_name} (escala relativa por camada)"
        linear.add_to(base_map)

        folium.LayerControl(collapsed=False).add_to(base_map)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        base_map.save(str(output_path))
        return output_path

    def _compute_clip_bounds(
        self,
        overlay_geojsons: Iterable[Dict],
    ) -> Optional[Tuple[float, float, float, float]]:
        geom_bounds = [extract_geometry_bounds(geojson_data) for geojson_data in overlay_geojsons]
        geom_bounds = [b for b in geom_bounds if b is not None]
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
        overlay_geojsons: Iterable[Dict],
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


def build_multi_map(
    index_paths: Sequence[Path],
    output_path: Path,
    cmap_name: str = "RdYlGn",
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    opacity: float = 0.75,
    overlays: Optional[Iterable[Path]] = None,
    tiles: str = "CartoDB positron",
    tile_attr: Optional[str] = None,
    padding_factor: float = 0.3,
    clip: bool = False,
    upsample: float = 1.0,
    sharpen: bool = False,
    sharpen_radius: float = 1.0,
    sharpen_amount: float = 1.2,
    smooth_radius: float = 0.0,
) -> Path:
    """Compatibility wrapper preserving the old function signature."""
    options = MultiIndexMapOptions(
        cmap_name=cmap_name,
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
    renderer = MultiIndexMapRenderer(options)
    return renderer.render(index_paths=index_paths, output_path=output_path, overlays=overlays)
