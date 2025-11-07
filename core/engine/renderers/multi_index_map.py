from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import json

import folium
import numpy as np
from branca.colormap import LinearColormap
from branca.element import MacroElement, Template
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
    enable_panel: bool = False


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
        layer_entries: List[Dict[str, str]] = []

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
            layer_entries.append({"name": Path(idx_path).stem.upper(), "layer_id": feature.get_name()})

        geo_layer_names: List[str] = []
        for geojson_data in overlay_geojsons:
            geo_layer = folium.GeoJson(
                data=geojson_data,
                name="AOI",
                style_function=lambda _: {"fillOpacity": 0, "color": "#3388ff", "weight": 3},
            )
            geo_layer.add_to(base_map)
            geo_layer_names.append(geo_layer.get_name())

        linear = LinearColormap(
            [colors.rgb2hex(colormaps[self.options.cmap_name](x)) for x in np.linspace(0, 1, 10)],
            vmin=0,
            vmax=1,
        )
        linear.caption = f"{self.options.cmap_name} (escala relativa por camada)"
        linear.add_to(base_map)

        if self.options.enable_panel and layer_entries:
            self._attach_panel(base_map, layer_entries, geo_layer_names)
        else:
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

        folium.TileLayer(
            tiles="https://api.mapbox.com/styles/v1/mapbox/satellite-streets-v12/tiles/256/{z}/{x}/{y}?access_token=pk.eyJ1IjoibWFwYm94IiwiYSI6ImNpamY4dnk3YTAyM3Z0eHBndTRvcXg1dmYifQ._K7HwvfVtZQwXu-WZp9lag",
            attr="Mapbox Satellite Streets",
            name="Mapbox",
            overlay=False,
            control=True,
            min_zoom=self.options.min_zoom,
            max_zoom=self.options.max_zoom,
            max_native_zoom=22,
        ).add_to(base_map)
        return base_map

    def _attach_panel(
        self,
        base_map: folium.Map,
        index_layers: Sequence[Dict[str, str]],
        geo_layer_names: Sequence[str],
    ) -> None:
        entries = [{"name": "Mapa base", "layer_id": "__base__"}]
        entries.extend(index_layers)
        panel = _IndexPanelMacro(
            map_id=base_map.get_name(),
            index_layers=entries,
            geo_layer_names=geo_layer_names,
        )
        base_map.get_root().add_child(panel)

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


class _IndexPanelMacro(MacroElement):
    def __init__(
        self,
        *,
        map_id: str,
        index_layers: Sequence[Dict[str, str]],
        geo_layer_names: Sequence[str],
    ) -> None:
        super().__init__()
        self._name = "IndexPanelMacro"
        self.map_id = map_id
        self.index_entries = list(index_layers)
        self.index_json = json.dumps(index_layers)
        self.geo_json = json.dumps(list(geo_layer_names))
        self._template = Template(
            """
{% macro html(this, kwargs) %}
<style>
    #index-panel {
        position: absolute;
        top: 75px;
        left: 15px;
        width: 320px;
        max-height: calc(100% - 30px);
        background: rgba(16, 22, 30, 0.95);
        color: #f1f1f1;
        border-radius: 8px;
        box-shadow: 0 12px 30px rgba(0,0,0,0.45);
        padding: 16px;
        overflow-y: auto;
        z-index: 1000;
        transition: opacity 0.2s ease;
    }
    #index-panel.hidden {
        opacity: 0;
        pointer-events: none;
    }
    #index-panel h3 {
        margin: 0 0 12px;
        font-size: 1.05rem;
        display: flex;
        align-items: center;
        justify-content: space-between;
    }
    #index-panel button {
        border: none;
        background: transparent;
        color: inherit;
        font-size: 1.2rem;
        cursor: pointer;
    }
    #index-panel ul {
        list-style: none;
        margin: 0 0 12px;
        padding: 0;
    }
    #index-panel li {
        padding: 8px 10px;
        margin-bottom: 6px;
        border-radius: 5px;
        background: rgba(255,255,255,0.05);
        cursor: pointer;
    }
    #index-panel li.active {
        background: #ffd43b;
        color: #1f1f1f;
        font-weight: 600;
    }
    #index-panel .talhao-box {
        border-radius: 5px;
        background: rgba(255,255,255,0.08);
        padding: 10px;
    }
    .talhao-tooltip {
        background: rgba(255, 255, 255, 0.95);
        color: #111;
        border-radius: 14px;
        border: 1px solid rgba(0,0,0,0.2);
        padding: 4px 12px;
        font-weight: 600;
        font-size: 1rem;
        box-shadow: 0 2px 6px rgba(0,0,0,0.25);
    }
</style>
<div id="index-panel" class="hidden">
    <h3>
        Índices por talhão
        <button id="index-panel-close">×</button>
    </h3>
    <div>
        <p><strong>Selecione um índice:</strong></p>
        <ul id="index-panel-list">
        {% for entry in this.index_entries %}
            <li data-layer-id="{{ entry.layer_id }}">{{ entry.name }}</li>
        {% endfor %}
        </ul>
    </div>
    <div class="talhao-box" id="talhao-info">
        <p>Selecione um talhão no mapa.</p>
    </div>
</div>
<script>
document.addEventListener('DOMContentLoaded', function() {
    const panel = document.getElementById('index-panel');
    const closeBtn = document.getElementById('index-panel-close');
    const infoBox = document.getElementById('talhao-info');
    const listItems = document.querySelectorAll('#index-panel-list li');
    const indexLayers = {{ this.index_json }};
    const geoLayerNames = {{ this.geo_json }};
    const overlayEntries = indexLayers.filter(entry => entry.layer_id !== "__base__");
    const hasBaseEntry = indexLayers.some(entry => entry.layer_id === "__base__");
    let mapObj = window["{{ this.map_id }}"];
    if (!mapObj) {
        return;
    }

    function highlightLayer(layer) {
        if (window.activePolygon && window.activePolygon !== layer) {
            window.activePolygon.setStyle({ color: "#3388ff", weight: 3 });
        }
        layer.setStyle({ color: "#ffd43b", weight: 5 });
        window.activePolygon = layer;
    }

    function setActiveLayer(layerId) {
        overlayEntries.forEach(entry => {
            const layer = window[entry.layer_id];
            if (!layer) return;
            if (layerId === entry.layer_id) {
                if (!mapObj.hasLayer(layer)) {
                    mapObj.addLayer(layer);
                }
            } else if (mapObj.hasLayer(layer)) {
                mapObj.removeLayer(layer);
            }
        });
        if (layerId === "__base__") {
            overlayEntries.forEach(entry => {
                const layer = window[entry.layer_id];
                if (layer && mapObj.hasLayer(layer)) {
                    mapObj.removeLayer(layer);
                }
            });
        }
        listItems.forEach(item => item.classList.toggle('active', item.dataset.layerId === layerId));
        panel.classList.remove('hidden');
    }

    function showTalhaoInfo(feature) {
        const props = feature.properties || {};
        infoBox.innerHTML = `
            <p><strong>ID:</strong> ${feature.id ?? '---'}</p>
            <p><strong>Área:</strong> ${props.area ?? '---'} ha</p>
            <p><strong>Variedade:</strong> ${props.variedade ?? '---'}</p>
            <p><strong>Observações:</strong> ${props.observacoes ?? '---'}</p>
        `;
        panel.classList.remove('hidden');
    }

    function wireGeojsonClicks() {
        const names = Array.isArray(geoLayerNames) ? geoLayerNames : [geoLayerNames];
        names.forEach(name => {
            const geoLayer = window[name];
            if (!geoLayer) return;
            geoLayer.eachLayer(function(layer) {
                layer.bindTooltip(
                    '<div class="talhao-tooltip">talhão-teste</div>',
                    {
                        permanent: true,
                        direction: 'top',
                        offset: [0, -12],
                        sticky: false,
                        className: '',
                        opacity: 1,
                    }
                );
                layer.on('click', function() {
                    highlightLayer(layer);
                    showTalhaoInfo(layer.feature || {});
                });
            });
        });
    }

    listItems.forEach(item => item.addEventListener('click', () => setActiveLayer(item.dataset.layerId)));
    closeBtn.addEventListener('click', () => panel.classList.add('hidden'));

    mapObj.whenReady(function() {
        if (listItems.length) {
            const defaultId = hasBaseEntry ? "__base__" : listItems[0].dataset.layerId;
            setActiveLayer(defaultId);
        }
        wireGeojsonClicks();
    });
});
</script>

        const activateDefault = () => {
            if (listItems.length) {
                setActiveLayer(listItems[0].dataset.layerId);
            }
            wireGeojsonClicks();
        };

        if (mapObj._loaded) {
            activateDefault();
        } else {
            mapObj.whenReady(activateDefault);
        }
        return true;
    }

    if (!initialize()) {
        const interval = setInterval(() => {
            if (initialize()) {
                clearInterval(interval);
            }
        }, 100);
        window.addEventListener("load", () => initialize());
    }
})();
</script>
{% endmacro %}
"""
        )


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
