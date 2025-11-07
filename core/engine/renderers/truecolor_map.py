from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import folium
import numpy as np
from branca.colormap import LinearColormap
from rasterio.enums import Resampling
from rasterio.warp import reproject
from scipy.ndimage import gaussian_filter

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
    stretch_lower: float = 1.0
    stretch_upper: float = 99.0
    smooth_radius: float = 0.8
    saturation_boost: float = 1.2
    gamma: float = 0.95
    channel_balance: bool = True
    zoom_start: int = 12
    min_zoom: int = 8
    max_zoom: int = 26
    max_native_zoom: int = 19
    show_esri: bool = True
    esri_opacity: float = 1.0


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
        base_map = folium.Map(
            location=[centre_lat, centre_lon],
            zoom_start=self.options.zoom_start,
            tiles=None,
            min_zoom=self.options.min_zoom,
            max_zoom=self.options.max_zoom,
        )

        # Adiciona Esri World Imagery como camada base padrão (opcional)
        native_limit = self.options.max_native_zoom
        if self.options.show_esri:
            folium.TileLayer(
                tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
                attr="Esri World Imagery",
                name="Esri World Imagery",
                overlay=False,
                control=True,
                max_zoom=self.options.max_zoom,
                max_native_zoom=native_limit,
                opacity=self.options.esri_opacity,
            ).add_to(base_map)

        # Camada alternativa (fallback) caso desejado
        if self.options.tiles.lower() != "none":
            folium.TileLayer(
                tiles=self.options.tiles,
                attr=self.options.tile_attr,
                name=self.options.tiles,
                overlay=False,
                control=True,
                max_zoom=self.options.max_zoom,
                max_native_zoom=native_limit,
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
        rgb = self._balance_channels(rgb)
        rgb = self._smooth_rgb(rgb)
        rgb = self._boost_saturation(rgb)
        rgb = self._apply_gamma(rgb)
        rgb = np.clip(rgb, 0.0, 1.0)
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

    def _balance_channels(self, rgb: np.ndarray) -> np.ndarray:
        if not self.options.channel_balance:
            return rgb
        mask = np.isfinite(rgb).all(axis=-1)
        if not np.any(mask):
            return rgb
        means = []
        for channel in range(rgb.shape[-1]):
            channel_values = rgb[..., channel][mask]
            if channel_values.size == 0:
                means.append(1.0)
            else:
                means.append(float(np.mean(channel_values)))
        target = float(np.mean(means))
        balanced = rgb.copy()
        for channel, mean in enumerate(means):
            if mean <= 0:
                continue
            scale = target / mean
            balanced[..., channel] *= scale
        return balanced

    def _smooth_rgb(self, rgb: np.ndarray) -> np.ndarray:
        sigma = max(self.options.smooth_radius, 0.0)
        if sigma <= 0:
            return rgb
        smoothed = np.empty_like(rgb)
        for channel in range(rgb.shape[-1]):
            smoothed[..., channel] = gaussian_filter(rgb[..., channel], sigma=sigma, mode="nearest")
        return smoothed

    def _boost_saturation(self, rgb: np.ndarray) -> np.ndarray:
        boost = max(self.options.saturation_boost, 0.0)
        if boost <= 0 or np.isclose(boost, 1.0):
            return rgb
        mean = np.mean(rgb, axis=-1, keepdims=True)
        enhanced = mean + (rgb - mean) * boost
        return np.clip(enhanced, 0.0, 1.0)

    def _apply_gamma(self, rgb: np.ndarray) -> np.ndarray:
        gamma = self.options.gamma
        if gamma <= 0 or np.isclose(gamma, 1.0):
            return rgb
        return np.power(np.clip(rgb, 0.0, 1.0), 1.0 / gamma)


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
    smooth_radius: float = 0.8,
    saturation_boost: float = 1.2,
    gamma: float = 0.95,
    show_esri: bool = True,
    esri_opacity: float = 1.0,
) -> Path:
    renderer = TrueColorRenderer(
        TrueColorOptions(
            tiles=tiles,
            tile_attr=tile_attr,
            padding_factor=padding_factor,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
            smooth_radius=smooth_radius,
            saturation_boost=saturation_boost,
            gamma=gamma,
            show_esri=show_esri,
            esri_opacity=esri_opacity,
        )
    )
    data = renderer.prepare(
        red_path=red_path,
        green_path=green_path,
        blue_path=blue_path,
        overlays=overlays,
    )
    return renderer.render_html(data, output_path)
