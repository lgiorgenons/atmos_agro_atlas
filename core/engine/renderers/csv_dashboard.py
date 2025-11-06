from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence

from .csv_map import CSVMapOptions, CSVMapRenderer
from .index_map import IndexMapData, IndexMapOptions, IndexMapRenderer
from .options import BaseMapOptions
from .truecolor_map import TrueColorOptions, TrueColorRenderer


@dataclass
class CSVDashboardOptions(BaseMapOptions):
    colormap: str = "RdYlGn"
    opacity: float = 0.75
    vmin: Optional[float] = None
    vmax: Optional[float] = None
    stretch_lower: float = 2.0
    stretch_upper: float = 98.0


class CSVDashboardRenderer:
    """Object-oriented renderer that composes true color and CSV layers into a tabbed dashboard."""

    def __init__(self, options: Optional[CSVDashboardOptions] = None):
        self.options = options or CSVDashboardOptions()

    def render(
        self,
        *,
        csv_dir: Path,
        red_path: Path,
        green_path: Path,
        blue_path: Path,
        overlays: Iterable[Path],
        output_path: Path,
    ) -> Path:
        csv_files = sorted(csv_dir.glob("*.csv"))
        if not csv_files:
            raise ValueError(f"Nenhum CSV encontrado em {csv_dir}")

        overlay_paths = list(overlays)
        layer_html_map: Dict[str, str] = {}

        truecolor_renderer = TrueColorRenderer(
            TrueColorOptions(
                tiles=self.options.tiles,
                tile_attr=self.options.tile_attr,
                padding_factor=self.options.padding_factor,
                sharpen=self.options.sharpen,
                sharpen_radius=self.options.sharpen_radius,
                sharpen_amount=self.options.sharpen_amount,
                stretch_lower=self.options.stretch_lower,
                stretch_upper=self.options.stretch_upper,
                smooth_radius=self.options.smooth_radius,
                zoom_start=self.options.zoom_start,
                min_zoom=self.options.min_zoom,
                max_zoom=self.options.max_zoom,
                max_native_zoom=self.options.max_native_zoom,
            )
        )
        truecolor_data = truecolor_renderer.prepare(
            red_path=red_path,
            green_path=green_path,
            blue_path=blue_path,
            overlays=overlay_paths,
        )
        layer_html_map["truecolor"] = self._render_map_to_iframe(
            lambda tmp_path: truecolor_renderer.render_html(truecolor_data, tmp_path)
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
                zoom_start=self.options.zoom_start,
                min_zoom=self.options.min_zoom,
                max_zoom=self.options.max_zoom,
                max_native_zoom=self.options.max_native_zoom,
            )
        )
        index_renderer = IndexMapRenderer(
            IndexMapOptions(
                cmap_name=self.options.colormap,
                vmin=self.options.vmin,
                vmax=self.options.vmax,
                opacity=self.options.opacity,
                tiles=self.options.tiles,
                tile_attr=self.options.tile_attr,
                padding_factor=self.options.padding_factor,
                clip=self.options.clip,
                upsample=self.options.upsample,
                smooth_radius=self.options.smooth_radius,
                sharpen=self.options.sharpen,
                sharpen_radius=self.options.sharpen_radius,
                sharpen_amount=self.options.sharpen_amount,
                zoom_start=self.options.zoom_start,
                min_zoom=self.options.min_zoom,
                max_zoom=self.options.max_zoom,
                max_native_zoom=self.options.max_native_zoom,
            )
        )

        for csv_path in csv_files:
            prepared = csv_renderer.prepare(csv_path=csv_path, overlays=overlay_paths)
            layer_html_map[prepared.index_name] = self._render_map_to_iframe(
                lambda tmp_path, prepared=prepared: index_renderer.render_html(prepared, tmp_path)
            )

        dashboard_html = self._build_dashboard_html(layer_html_map)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(dashboard_html, encoding="utf-8")
        return output_path

    @staticmethod
    def _render_map_to_iframe(writer) -> str:
        with tempfile.NamedTemporaryFile(suffix=".html", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
        try:
            writer(tmp_path)
            html = tmp_path.read_text(encoding="utf-8")
        finally:
            tmp_path.unlink(missing_ok=True)
        return html

    @staticmethod
    def _build_dashboard_html(layer_html_map: Dict[str, str], width: str = "100%", height: str = "600px") -> str:
        tabs_html = "".join(f"<li><a href='#{key}'>{key}</a></li>" for key in layer_html_map.keys())
        content_html = "".join(f"<div id='{key}' class='tab-content'>{html}</div>" for key, html in layer_html_map.items())
        return f"""
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="utf-8" />
    <title>Dashboard Indices Sentinel-2</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; }}
        .tabs {{ list-style: none; margin: 0; padding: 0; display: flex; background: #2b3d4f; }}
        .tabs li {{ flex: 1; }}
        .tabs a {{
            display: block;
            padding: 12px;
            color: #fff;
            text-align: center;
            text-decoration: none;
            transition: background 0.2s;
        }}
        .tabs a.active, .tabs a:hover {{ background: #1a252f; }}
        .tab-content {{ display: none; width: {width}; height: {height}; }}
        .tab-content.active {{ display: block; }}
        iframe {{ border: none; width: 100%; height: 100%; }}
    </style>
</head>
<body>
    <ul class="tabs">
        {tabs_html}
    </ul>
    {content_html}
    <script>
        const tabs = document.querySelectorAll('.tabs a');
        const contents = document.querySelectorAll('.tab-content');
        function activateTab(targetId) {{
            contents.forEach(content => content.classList.remove('active'));
            tabs.forEach(tab => tab.classList.remove('active'));
            document.getElementById(targetId).classList.add('active');
            document.querySelector(`.tabs a[href='#${{targetId}}']`).classList.add('active');
        }}
        tabs.forEach(tab => {{
            tab.addEventListener('click', event => {{
                event.preventDefault();
                const targetId = tab.getAttribute('href').substring(1);
                activateTab(targetId);
            }});
        }});
        if (tabs.length > 0) {{
            const firstId = tabs[0].getAttribute('href').substring(1);
            activateTab(firstId);
        }}
    </script>
</body>
</html>
""".strip()
