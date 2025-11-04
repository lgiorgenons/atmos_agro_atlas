from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

import folium
from branca.colormap import LinearColormap

from .csv_map import CSVMapOptions, CSVMapRenderer
from .truecolor_map import TrueColorOptions, TrueColorRenderer
from .raster import generate_rgba


@dataclass
class OverlayMapOptions:
    tiles: str = "CartoDB positron"
    tile_attr: Optional[str] = None
    padding_factor: float = 0.3
    clip: bool = False
    colormap: str = "RdYlGn"
    opacity: float = 0.75
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    upsample: float = 1.0
    sharpen: bool = False
    sharpen_radius: float = 1.0
    sharpen_amount: float = 1.3
    smooth_radius: float = 0.0


class TrueColorOverlayRenderer:
    """Object-oriented renderer for true color maps with CSV overlays."""

    def __init__(self, options: Optional[OverlayMapOptions] = None):
        self.options = options or OverlayMapOptions()

    def render(
        self,
        *,
        csv_dir: Path,
        red_path: Path,
        green_path: Path,
        blue_path: Path,
        overlays: Iterable[Path],
        output_path: Optional[Path] = None,
        indices: Optional[Sequence[str]] = None,
    ) -> folium.Map:
        overlay_paths = list(overlays)
        truecolor_renderer = TrueColorRenderer(
            TrueColorOptions(
                tiles=self.options.tiles,
                tile_attr=self.options.tile_attr,
                padding_factor=self.options.padding_factor,
                sharpen=self.options.sharpen,
                sharpen_radius=self.options.sharpen_radius,
                sharpen_amount=self.options.sharpen_amount,
            )
        )
        truecolor_data = truecolor_renderer.prepare(
            red_path=red_path,
            green_path=green_path,
            blue_path=blue_path,
            overlays=overlay_paths,
        )

        csv_renderer = CSVMapRenderer(
            CSVMapOptions(
                colormap=self.options.colormap,
                vmin=self.options.vmin,
                vmax=self.options.vmax,
                opacity=self.options.opacity,
                tiles=self.options.tiles,
                tile_attr=self.options.tile_attr,
                padding_factor=self.options.padding_factor,
                clip=self.options.clip,
                upsample=self.options.upsample,
                sharpen=self.options.sharpen,
                sharpen_radius=self.options.sharpen_radius,
                sharpen_amount=self.options.sharpen_amount,
                smooth_radius=self.options.smooth_radius,
            )
        )

        csv_files = sorted(csv_dir.glob("*.csv"))
        if indices:
            requested = set(indices)
            csv_files = [path for path in csv_files if path.stem in requested]
        if not csv_files:
            raise RuntimeError(f"Nenhum CSV encontrado em {csv_dir} (verifique filtros, se houver).")

        min_lon, min_lat, max_lon, max_lat = truecolor_data.bounds
        centre_lat = (min_lat + max_lat) / 2
        centre_lon = (min_lon + max_lon) / 2

        base_map = self._build_base_map(centre_lat, centre_lon)
        folium.raster_layers.ImageOverlay(
            image=truecolor_data.image,
            bounds=[[min_lat, min_lon], [max_lat, max_lon]],
            opacity=1.0,
            name="True color",
            control=False,
        ).add_to(base_map)

        for geojson_data in truecolor_data.overlays:
            folium.GeoJson(data=geojson_data, name="AOI", style_function=lambda _: {"fillOpacity": 0}).add_to(base_map)

        for idx, csv_path in enumerate(csv_files):
            index_data = csv_renderer.prepare(csv_path=csv_path, overlays=overlay_paths)
            image, _, _ = generate_rgba(
                index_data.data,
                self.options.colormap,
                self.options.vmin,
                self.options.vmax,
                self.options.opacity,
            )
            bounds = index_data.clip_bounds if index_data.clip_bounds is not None else index_data.bounds

            feature = folium.FeatureGroup(name=csv_path.stem, show=(idx == 0))
            folium.raster_layers.ImageOverlay(
                image=image,
                bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
                opacity=1.0,
            ).add_to(feature)
            feature.add_to(base_map)

        legend = LinearColormap(["#000000", "#FFFFFF"], vmin=0, vmax=1)
        legend.caption = f"{self.options.colormap} (escala relativa)"
        legend.add_to(base_map)

        folium.LayerControl(collapsed=False).add_to(base_map)
        base_map.fit_bounds([[min_lat, min_lon], [max_lat, max_lon]])

        if output_path is not None:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            base_map.save(str(output_path))
        return base_map

    def _build_base_map(self, centre_lat: float, centre_lon: float) -> folium.Map:
        if self.options.tiles.lower() == "none":
            return folium.Map(location=[centre_lat, centre_lon], zoom_start=12, tiles=None)
        return folium.Map(location=[centre_lat, centre_lon], zoom_start=12, tiles=self.options.tiles, attr=self.options.tile_attr)


def build_overlay_map(
    csv_dir: Path,
    red_path: Path,
    green_path: Path,
    blue_path: Path,
    overlays: Iterable[Path],
    *,
    clip: bool,
    padding: float,
    tiles: str,
    tile_attr: Optional[str],
    colormap: str,
    opacity: float,
    vmin: Optional[float],
    vmax: Optional[float],
    upsample: float,
    sharpen: bool,
    sharpen_radius: float,
    sharpen_amount: float,
    smooth_radius: float,
    indices: Optional[Sequence[str]] = None,
    output_path: Optional[Path] = None,
) -> Path:
    renderer = TrueColorOverlayRenderer(
        OverlayMapOptions(
            tiles=tiles,
            tile_attr=tile_attr,
            padding_factor=padding,
            clip=clip,
            colormap=colormap,
            opacity=opacity,
            vmin=vmin,
            vmax=vmax,
            upsample=upsample,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
            smooth_radius=smooth_radius,
        )
    )
    target_output = output_path or Path("mapas/overlay_indices.html")
    return renderer.render(
        csv_dir=csv_dir,
        red_path=red_path,
        green_path=green_path,
        blue_path=blue_path,
        overlays=overlays,
        output_path=target_output,
        indices=indices,
    )
