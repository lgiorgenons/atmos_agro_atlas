from __future__ import annotations

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.colors import Normalize

from .geoutils import extract_geometry_bounds, iterate_geometries, load_geojson
from .raster import load_raster

BAND_ORDER = [
    ("coastal", "B01 Coastal/Aerosol"),
    ("blue", "B02 Blue"),
    ("green", "B03 Green"),
    ("red", "B04 Red"),
    ("rededge1", "B05 Red-edge 1"),
    ("rededge2", "B06 Red-edge 2"),
    ("rededge3", "B07 Red-edge 3"),
    ("nir", "B08 NIR"),
    ("rededge4", "B8A Narrow NIR"),
    ("water_vapor", "B09 Water Vapour"),
    ("cirrus", "B10 Cirrus"),
    ("swir1", "B11 SWIR 1"),
    ("swir2", "B12 SWIR 2"),
]


@dataclass
class BandGalleryOptions:
    stretch_percentiles: Tuple[float, float] = (2.0, 98.0)


@dataclass
class BandGalleryEntry:
    label: str
    band_key: str
    image_base64: str


class BandGalleryRenderer:
    """Object-oriented renderer for the Sentinel-2 band gallery."""

    def __init__(self, options: Optional[BandGalleryOptions] = None):
        self.options = options or BandGalleryOptions()

    def render(
        self,
        product_dir: Path,
        output_html: Path,
        geojson_path: Optional[Path] = None,
    ) -> Path:
        geojson = load_geojson(geojson_path) if geojson_path else None
        clip_bounds = extract_geometry_bounds(geojson) if geojson else None

        entries: List[BandGalleryEntry] = []
        extent: Optional[Tuple[float, float, float, float]] = None

        for band_key, band_label in BAND_ORDER:
            band_path = product_dir / f"{band_key}.tif"
            if not band_path.exists():
                continue

            data, _, bounds = load_raster(band_path, clip_bounds_wgs84=clip_bounds)
            if extent is None:
                extent = bounds

            valid = np.isfinite(data)
            if not np.any(valid):
                continue

            vmin, vmax = np.nanpercentile(data[valid], self.options.stretch_percentiles)
            norm = Normalize(vmin=vmin, vmax=vmax, clip=True)

            fig, ax = plt.subplots(figsize=(4, 4))
            if extent is not None:
                min_lon, min_lat, max_lon, max_lat = extent
                ax.imshow(norm(data), cmap="gray", extent=[min_lon, max_lon, min_lat, max_lat], origin="lower")
                ax.set_xlim(min_lon, max_lon)
                ax.set_ylim(min_lat, max_lat)
                ax.set_aspect("equal", adjustable="box")
            else:
                ax.imshow(norm(data), cmap="gray")

            if geojson:
                for geom in iterate_geometries(geojson):
                    xs = [coord[0] for coord in geom["coordinates"][0]]
                    ys = [coord[1] for coord in geom["coordinates"][0]]
                    ax.plot(xs, ys, color="cyan", linewidth=1)

            ax.set_title(f"{band_label}\n({band_key}.tif)\n[{vmin:.2f}, {vmax:.2f}]")
            ax.axis("off")

            image_b64 = self._figure_to_base64(fig)
            entries.append(BandGalleryEntry(band_label, band_key, image_b64))

        html = self._build_html(product_dir.name, entries, geojson_path)
        output_html.parent.mkdir(parents=True, exist_ok=True)
        output_html.write_text(html, encoding="utf-8")
        return output_html

    @staticmethod
    def _figure_to_base64(fig: plt.Figure) -> str:
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", dpi=150)
        plt.close(fig)
        buf.seek(0)
        encoded = base64.b64encode(buf.read()).decode("utf-8")
        return f"data:image/png;base64,{encoded}"

    @staticmethod
    def _build_html(
        product_name: str,
        entries: Sequence[BandGalleryEntry],
        geojson_path: Optional[Path],
    ) -> str:
        html_parts = [
            "<html><head><meta charset='utf-8'><title>Sentinel-2 Band Gallery</title>",
            "<style>body { font-family: sans-serif; background:#111; color:#eee;}",
            ".grid { display: flex; flex-wrap: wrap; gap: 12px;}",
            ".band { background:#222; padding: 8px; border-radius: 6px; width: 320px; text-align:center;}",
            ".band img { width:100%; border-radius:4px; }",
            "</style></head><body>",
            f"<h1>Sentinel-2 Band Gallery - {product_name}</h1>",
        ]
        if geojson_path:
            html_parts.append(f"<p>Recorte aplicado com base no GeoJSON: {geojson_path}</p>")
        html_parts.append("<div class='grid'>")
        for entry in entries:
            html_parts.append(
                f"<div class='band'><img src='{entry.image_base64}' alt='{entry.band_key}'/>"
                f"<div>{entry.label}</div></div>"
            )
        html_parts.append("</div></body></html>")
        return "\n".join(html_parts)


def build_gallery(
    product_dir: Path,
    output_html: Path,
    geojson_path: Optional[Path],
    stretch_percentiles: Tuple[float, float] = (2, 98),
) -> Path:
    renderer = BandGalleryRenderer(BandGalleryOptions(stretch_percentiles=stretch_percentiles))
    return renderer.render(product_dir=product_dir, output_html=output_html, geojson_path=geojson_path)
