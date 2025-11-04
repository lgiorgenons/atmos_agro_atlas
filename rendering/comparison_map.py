from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence

import folium
import numpy as np
from branca.colormap import LinearColormap
from folium.plugins import DualMap
from matplotlib import colormaps, colors

from canasat.rendering.geoutils import load_geojson
from canasat.rendering.index_map import IndexMapOptions, IndexMapRenderer
from canasat.rendering.raster import generate_rgba


@dataclass
class ComparisonMapOptions:
    colormap: str = "RdYlGn"
    opacity: float = 0.75
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    sharpen: bool = False
    sharpen_radius: float = 1.2
    sharpen_amount: float = 1.5
    tiles: str = "OpenStreetMap"
    tile_attr: Optional[str] = None
    max_zoom: int = 19


class ComparisonMapRenderer:
    """Object-oriented renderer for dual-map comparisons."""

    def __init__(self, options: Optional[ComparisonMapOptions] = None):
        self.options = options or ComparisonMapOptions()

    def render(
        self,
        index_path: Path,
        output_path: Path,
        overlays: Optional[Iterable[Path]] = None,
    ) -> Path:
        overlay_paths = list(overlays or [])
        index_renderer = IndexMapRenderer(
            IndexMapOptions(
                cmap_name=self.options.colormap,
                vmin=self.options.vmin,
                vmax=self.options.vmax,
                opacity=self.options.opacity,
                tiles=self.options.tiles,
                tile_attr=self.options.tile_attr,
                clip=False,
                upsample=1.0,
                sharpen=self.options.sharpen,
                sharpen_radius=self.options.sharpen_radius,
                sharpen_amount=self.options.sharpen_amount,
            )
        )
        prepared = index_renderer.prepare(index_path=index_path, overlays=overlay_paths)
        bounds = prepared.clip_bounds if prepared.clip_bounds is not None else prepared.bounds
        min_lon, min_lat, max_lon, max_lat = bounds
        centre_lat = (min_lat + max_lat) / 2
        centre_lon = (min_lon + max_lon) / 2

        image, min_value, max_value = generate_rgba(
            data=prepared.data,
            cmap_name=self.options.colormap,
            vmin=self.options.vmin,
            vmax=self.options.vmax,
            opacity=self.options.opacity,
        )

        dual_map = DualMap(
            location=[centre_lat, centre_lon],
            zoom_start=14,
            tiles=None,
            max_zoom=self.options.max_zoom,
        )

        self._add_basemap(dual_map.m1)
        self._add_basemap(dual_map.m2)

        folium.raster_layers.ImageOverlay(
            image=image,
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            opacity=1.0,
            name=index_path.stem.upper(),
        ).add_to(dual_map.m2)

        overlay_geojsons = [load_geojson(path) for path in overlay_paths]
        for data_geo in overlay_geojsons:
            folium.GeoJson(data=data_geo, name="AOI", style_function=lambda _: {"fillOpacity": 0}).add_to(dual_map.m1)
            folium.GeoJson(data=data_geo, name="AOI", style_function=lambda _: {"fillOpacity": 0}).add_to(dual_map.m2)

        colorbar = LinearColormap(
            [colors.rgb2hex(colormaps[self.options.colormap](x)) for x in np.linspace(0, 1, 10)],
            vmin=min_value,
            vmax=max_value,
        )
        colorbar.caption = f"{index_path.stem.upper()} (min={min_value:.3f}, max={max_value:.3f})"
        colorbar.add_to(dual_map.m2)

        dual_map.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])
        folium.LayerControl(position="topright").add_to(dual_map.m1)
        folium.LayerControl(position="topright").add_to(dual_map.m2)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        dual_map.save(str(output_path))
        return output_path

    def _add_basemap(self, map_obj: folium.Map) -> None:
        if self.options.tiles.lower() != "none":
            folium.TileLayer(
                tiles=self.options.tiles,
                attr=self.options.tile_attr,
                name="Basemap",
                control=False,
            ).add_to(map_obj)
        folium.TileLayer(
            tiles="https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}",
            attr="Esri World Imagery",
            name="Esri World Imagery",
            overlay=False,
            control=True,
        ).add_to(map_obj)


def build_comparison_map(
    index_path: Path,
    output_path: Path,
    geojson_paths: Iterable[Path],
    cmap_name: str = "RdYlGn",
    opacity: float = 0.75,
    vmin: Optional[float] = None,
    vmax: Optional[float] = None,
    sharpen: bool = False,
    sharpen_radius: float = 1.2,
    sharpen_amount: float = 1.5,
    basemap: str = "OpenStreetMap",
    attr: Optional[str] = None,
    max_zoom: int = 19,
) -> Path:
    renderer = ComparisonMapRenderer(
        ComparisonMapOptions(
            colormap=cmap_name,
            opacity=opacity,
            vmin=vmin,
            vmax=vmax,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
            tiles=basemap,
            tile_attr=attr,
            max_zoom=max_zoom,
        )
    )
    return renderer.render(index_path=index_path, output_path=output_path, overlays=geojson_paths)
