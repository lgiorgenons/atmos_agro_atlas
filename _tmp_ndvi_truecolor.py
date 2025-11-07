from pathlib import Path
import folium
from core.engine.renderers.truecolor_map import TrueColorRenderer, TrueColorOptions
from core.engine.renderers.index_map import IndexMapRenderer, IndexMapOptions
from core.engine.renderers.raster import generate_rgba
from core.engine.renderers.geoutils import load_geojson

product_dir = Path('data/processed/S2B_MSIL2A_20251025T132229_N0511_R038_T22KHB_20251025T151112')
red_path = product_dir / 'red.tif'
green_path = product_dir / 'green.tif'
blue_path = product_dir / 'blue.tif'
ndvi_path = product_dir / 'indices/ndvi.tif'
aoi_path = Path('dados/map.geojson')

true_opts = TrueColorOptions(
    tiles='CartoDB positron',
    padding_factor=0.0,
    sharpen=True,
    sharpen_radius=1.0,
    sharpen_amount=1.2,
    min_zoom=9,
    max_zoom=21,
    zoom_start=15,
)
true_renderer = TrueColorRenderer(true_opts)
true_data = true_renderer.prepare(red_path=red_path, green_path=green_path, blue_path=blue_path, overlays=None)

min_lon, min_lat, max_lon, max_lat = true_data.bounds
centre_lat = (min_lat + max_lat) / 2
centre_lon = (min_lon + max_lon) / 2
base_map = true_renderer._build_base_map(centre_lat, centre_lon)
folium.raster_layers.ImageOverlay(
    image=true_data.image,
    bounds=[[min_lat, min_lon], [max_lat, max_lon]],
    opacity=1.0,
    name='True color',
).add_to(base_map)

if aoi_path.exists():
    aoi_geojson = load_geojson(aoi_path)
    folium.GeoJson(data=aoi_geojson, name='AOI', style_function=lambda _: {"fillOpacity": 0}).add_to(base_map)

ndvi_opts = IndexMapOptions(
    cmap_name='RdYlGn',
    opacity=0.75,
    clip=True,
    padding_factor=0.02,
    upsample=4.0,
    smooth_radius=1.0,
)
index_renderer = IndexMapRenderer(ndvi_opts)
index_data = index_renderer.prepare(index_path=ndvi_path, overlays=[aoi_path])
rgba, _, _ = generate_rgba(index_data.data, ndvi_opts.cmap_name, ndvi_opts.vmin, ndvi_opts.vmax, ndvi_opts.opacity)
bounds = index_data.clip_bounds if index_data.clip_bounds is not None else index_data.bounds
ndvi_layer = folium.FeatureGroup(name='NDVI', show=True)
folium.raster_layers.ImageOverlay(
    image=rgba,
    bounds=[[bounds[1], bounds[0]], [bounds[3], bounds[2]]],
    opacity=1.0,
).add_to(ndvi_layer)
ndvi_layer.add_to(base_map)

folium.LayerControl(collapsed=False).add_to(base_map)
output_path = Path('mapas/ndvi_truecolor_overlay.html')
output_path.parent.mkdir(parents=True, exist_ok=True)
base_map.save(str(output_path))
print(f'Mapa salvo em {output_path}')
