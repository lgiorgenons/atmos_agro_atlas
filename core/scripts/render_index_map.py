from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from core.cfg.settings import AppConfig
from core.engine.renderers.index_map import IndexMapOptions, IndexMapRenderer


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um mapa HTML (e opcionalmente CSV) para um índice rasterizado."
    )
    parser.add_argument(
        "--index",
        required=True,
        type=Path,
        help="Arquivo raster do índice (GeoTIFF).",
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=Path("dados/map.geojson"),
        help="GeoJSON usado como overlay e para recorte do mapa (default: dados/map.geojson).",
    )
    parser.add_argument(
        "--no-geojson",
        action="store_true",
        help="Não adiciona overlay GeoJSON e desativa recorte automático.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Arquivo HTML de saída. Default: <MAPAS_DIR>/<nome_indice>_map.html.",
    )
    parser.add_argument(
        "--csv",
        nargs="?",
        const="auto",
        help="Exporta os pontos válidos para CSV. Passe o caminho ou deixe vazio para usar <TABELAS_DIR>/<indice>.csv.",
    )
    parser.add_argument(
        "--cmap",
        default="RdYlGn",
        help="Colormap Matplotlib utilizado para o gradiente (default: RdYlGn).",
    )
    parser.add_argument(
        "--vmin",
        type=float,
        help="Valor mínimo fixo do colormap. Se omitido, usa o mínimo do raster.",
    )
    parser.add_argument(
        "--vmax",
        type=float,
        help="Valor máximo fixo do colormap. Se omitido, usa o máximo do raster.",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        default=0.75,
        help="Opacidade do overlay (0-1). Default: 0.75.",
    )
    parser.add_argument(
        "--tiles",
        default="CartoDB positron",
        help="Camada base do Folium (default: CartoDB positron).",
    )
    parser.add_argument(
        "--tile-attr",
        default="Map tiles by CartoDB, imagery © Esri",
        help="Atribuição exibida para a camada base.",
    )
    parser.add_argument(
        "--no-basemap",
        action="store_true",
        help="Remove a camada base (tile).",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.3,
        help="Fator de padding aplicado ao recorte com base no GeoJSON. Default: 0.3.",
    )
    parser.add_argument(
        "--clip",
        action="store_true",
        default=True,
        help="Ativa recorte do raster usando o GeoJSON (default).",
    )
    parser.add_argument(
        "--no-clip",
        action="store_false",
        dest="clip",
        help="Desativa recorte do raster pelo GeoJSON.",
    )
    parser.add_argument(
        "--upsample",
        type=float,
        default=12.0,
        help="Fator de upsample antes da suavização (default: 12).",
    )
    parser.add_argument(
        "--smooth-radius",
        type=float,
        default=1.0,
        help="Raio da suavização gaussiana (default: 1.0).",
    )
    parser.add_argument(
        "--sharpen",
        action="store_true",
        default=True,
        help="Aplica filtro de nitidez (default).",
    )
    parser.add_argument(
        "--no-sharpen",
        action="store_false",
        dest="sharpen",
        help="Desativa o filtro de nitidez.",
    )
    parser.add_argument(
        "--sharpen-radius",
        type=float,
        default=1.2,
        help="Raio do filtro de nitidez (default: 1.2).",
    )
    parser.add_argument(
        "--sharpen-amount",
        type=float,
        default=1.5,
        help="Intensidade do filtro de nitidez (default: 1.5).",
    )
    parser.add_argument(
        "--zoom-start",
        type=int,
        default=14,
        help="Zoom inicial do mapa (default: 14).",
    )
    parser.add_argument(
        "--min-zoom",
        type=int,
        default=1,
        help="Zoom mínimo permitido no mapa (default: 1).",
    )
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=28,
        help="Zoom máximo permitido no mapa (default: 28).",
    )
    parser.add_argument(
        "--max-native-zoom",
        type=int,
        default=19,
        help="Zoom máximo nativo disponível na camada base (default: 19). Tiles acima disso serão ampliados.",
    )
    parser.add_argument(
        "--allow-basemap-stretch",
        action="store_true",
        help="Ignora limites de native zoom do basemap e mantém tiles mesmo quando o provedor retornar placeholders.",
    )
    return parser.parse_args(argv)


def build_options(args: argparse.Namespace) -> IndexMapOptions:
    tiles = "none" if args.no_basemap else args.tiles
    return IndexMapOptions(
        cmap_name=args.cmap,
        vmin=args.vmin,
        vmax=args.vmax,
        opacity=args.opacity,
        tiles=tiles,
        tile_attr=args.tile_attr if not args.no_basemap else None,
        padding_factor=args.padding,
        clip=args.clip and not args.no_geojson,
        upsample=max(args.upsample, 1.0),
        smooth_radius=max(args.smooth_radius, 0.0),
        sharpen=args.sharpen,
        sharpen_radius=args.sharpen_radius,
        sharpen_amount=args.sharpen_amount,
        zoom_start=args.zoom_start,
        min_zoom=args.min_zoom,
        max_zoom=args.max_zoom,
        max_native_zoom=args.max_native_zoom,
        allow_basemap_stretch=args.allow_basemap_stretch,
    )


def resolve_paths(args: argparse.Namespace, cfg: AppConfig) -> tuple[Path, Path, Optional[Path], Optional[Path]]:
    index_path = args.index.expanduser().resolve()
    if not index_path.exists():
        raise FileNotFoundError(f"Index raster not found: {index_path}")

    output_html = (
        args.output.expanduser().resolve()
        if args.output
        else (cfg.MAPAS_DIR / f"{index_path.stem}_map.html").resolve()
    )
    output_html.parent.mkdir(parents=True, exist_ok=True)

    csv_path: Optional[Path] = None
    if args.csv:
        if args.csv == "auto":
            csv_path = (cfg.TABELAS_DIR / f"{index_path.stem}.csv").resolve()
        else:
            csv_path = Path(args.csv).expanduser().resolve()
        csv_path.parent.mkdir(parents=True, exist_ok=True)

    geojson_path: Optional[Path] = None
    if not args.no_geojson and args.geojson is not None:
        geojson_path = args.geojson.expanduser().resolve()
        if not geojson_path.exists():
            raise FileNotFoundError(f"GeoJSON overlay not found: {geojson_path}")

    return index_path, output_html, csv_path, geojson_path


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    cfg = AppConfig()
    index_path, output_html, csv_path, geojson_path = resolve_paths(args, cfg)

    overlays = [geojson_path] if geojson_path is not None else None
    options = build_options(args)
    renderer = IndexMapRenderer(options)
    prepared = renderer.prepare(index_path=index_path, overlays=overlays)

    renderer.render_html(prepared, output_html)
    message = [f"Mapa gerado em {output_html}"]

    if csv_path is not None:
        renderer.export_csv(prepared, csv_path)
        message.append(f"CSV exportado para {csv_path}")

    print(" | ".join(message))


if __name__ == "__main__":
    main()
