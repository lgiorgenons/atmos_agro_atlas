from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import folium
import numpy as np
from branca.colormap import LinearColormap
from rasterio.enums import Resampling
from rasterio.warp import reproject

from .geoutils import extract_geometry_bounds, load_geojson
from .raster import TARGET_CRS, apply_unsharp_mask, load_raster


@dataclass
class TrueColorOptions:
    tiles: str = "CartoDB positron"
    tile_attr: Optional[str] = None
    padding_factor: float = 0.3
    sharpen: bool = False
    sharpen_radius: float = 1.0
    sharpen_amount: float = 1.2
    stretch_lower: float = 2.0
    stretch_upper: float = 98.0
    zoom_start: int = 12


@dataclass
class TrueColorData:
    image: np.ndarray
    bounds: Tuple[float, float, float, float]
    overlays: List[Dict]


class TrueColorRenderer:
    """Renderer OO para composicoes RGB (true color)."""

    def __init__(self, options: Optional[TrueColorOptions] = None):
        self.options = options or TrueColorOptions()

    def prepare(
        self,
        *,
        red_path: Path,
        green_path: Path,
        blue_path: Path,
        overlays: Optional[Iterable[Path]] = None,
    ) -> TrueColorData:
        overlay_geojsons = [load_geojson(path) for path in (overlays or [])]
        clip_bounds = self._compute_clip_bounds(overlay_geojsons)

        red_array, base_transform, bounds = load_raster(red_path, clip_bounds_wgs84=clip_bounds)
        green_array, green_transform, _ = load_raster(green_path, clip_bounds_wgs84=clip_bounds)
        blue_array, blue_transform, _ = load_raster(blue_path, clip_bounds_wgs84=clip_bounds)

        green_array = self._reproject_to_base(green_array, green_transform, base_transform, red_array.shape)
        blue_array = self._reproject_to_base(blue_array, blue_transform, base_transform, red_array.shape)

        if self.options.sharpen:
            red_array = apply_unsharp_mask(red_array, self.options.sharpen_radius, self.options.sharpen_amount)
            green_array = apply_unsharp_mask(green_array, self.options.sharpen_radius, self.options.sharpen_amount)
            blue_array = apply_unsharp_mask(blue_array, self.options.sharpen_radius, self.options.sharpen_amount)

        rgb_image = self._create_rgb_image(red_array, green_array, blue_array)

        if clip_bounds is not None:
            bounds = clip_bounds

        return TrueColorData(
            image=rgb_image,
            bounds=bounds,
            overlays=overlay_geojsons,
        )

    def render_html(self, data: TrueColorData, output_path: Path) -> Path:
        min_lon, min_lat, max_lon, max_lat = data.bounds
        centre_lat = (min_lat + max_lat) / 2
        centre_lon = (min_lon + max_lon) / 2

        base_map = self._build_base_map(centre_lat, centre_lon)

        folium.raster_layers.ImageOverlay(
            image=data.image,
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            opacity=1.0,
            name="True color",
        ).add_to(base_map)

        for geojson_data in data.overlays:
            folium.GeoJson(data=geojson_data, name="AOI", style_function=lambda _: {"fillOpacity": 0}).add_to(base_map)

        legend = LinearColormap(["#000000", "#FFFFFF"], vmin=0, vmax=255)
        legend.caption = f"Composicao RGB ({int(self.options.stretch_lower)}-{int(self.options.stretch_upper)}%)"
        legend.add_to(base_map)

        folium.LayerControl().add_to(base_map)
        base_map.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

        output_path.parent.mkdir(parents=True, exist_ok=True)
        base_map.save(str(output_path))
        return output_path

    def _build_base_map(self, centre_lat: float, centre_lon: float) -> folium.Map:
        if self.options.tiles.lower() == "none":
            return folium.Map(location=[centre_lat, centre_lon], zoom_start=self.options.zoom_start, tiles=None)
        base_map = folium.Map(
            location=[centre_lat, centre_lon],
            zoom_start=self.options.zoom_start,
            tiles=self.options.tiles,
            attr=self.options.tile_attr,
        )
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Esri World Imagery",
            overlay=False,
            control=True,
        ).add_to(base_map)
        return base_map

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

    def _reproject_to_base(
        self,
        data: np.ndarray,
        src_transform,
        dst_transform,
        dst_shape: Tuple[int, int],
    ) -> np.ndarray:
        destination = np.full(dst_shape, np.nan, dtype=np.float32)
        reproject(
            source=data,
            destination=destination,
            src_transform=src_transform,
            src_crs=TARGET_CRS,
            dst_transform=dst_transform,
            dst_crs=TARGET_CRS,
            src_nodata=np.nan,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )
        return destination

    def _create_rgb_image(self, red: np.ndarray, green: np.ndarray, blue: np.ndarray) -> np.ndarray:
        r = self._stretch_array(red)
        g = self._stretch_array(green)
        b = self._stretch_array(blue)
        rgb = np.stack([r, g, b], axis=-1)
        return (rgb * 255).astype(np.uint8)

    def _stretch_array(self, array: np.ndarray) -> np.ndarray:
        finite = np.isfinite(array)
        if not np.any(finite):
            raise RuntimeError("Banda sem valores validos para renderizacao.")

        lower = float(self.options.stretch_lower)
        upper = float(self.options.stretch_upper)
        vmin = np.percentile(array[finite], lower)
        vmax = np.percentile(array[finite], upper)
        if np.isclose(vmin, vmax):
            vmax = vmin + 1e-3
        stretched = np.clip((array - vmin) / (vmax - vmin), 0, 1)
        stretched[~finite] = 0
        return stretched.astype(np.float32)


def build_truecolor_map(
    red_path: Path,
    green_path: Path,
    blue_path: Path,
    output_path: Path,
    overlays: Optional[Iterable[Path]] = None,
    tiles: str = "CartoDB positron",
    tile_attr: Optional[str] = None,
    padding_factor: float = 0.3,
    sharpen: bool = False,
    sharpen_radius: float = 1.0,
    sharpen_amount: float = 1.2,
) -> Path:
    renderer = TrueColorRenderer(
        TrueColorOptions(
            tiles=tiles,
            tile_attr=tile_attr,
            padding_factor=padding_factor,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
        )
    )
    data = renderer.prepare(
        red_path=red_path,
        green_path=green_path,
        blue_path=blue_path,
        overlays=overlays,
    )
    return renderer.render_html(data, output_path)
