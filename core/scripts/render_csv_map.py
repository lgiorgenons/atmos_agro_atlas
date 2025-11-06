from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional

from core.cfg.settings import AppConfig
from core.engine.renderers.csv_map import CSVMapOptions, CSVMapRenderer


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reconstrói um mapa a partir de um CSV de pontos (lon, lat, value) e gera um HTML com tiles Folium."
    )
    parser.add_argument(
        "--csv",
        required=True,
        type=Path,
        help="Arquivo CSV com colunas longitude, latitude, value.",
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=Path("dados/map.geojson"),
        help="GeoJSON usado como overlay e recorte (default: dados/map.geojson).",
    )
    parser.add_argument(
        "--no-geojson",
        action="store_true",
        help="Não usa overlay GeoJSON (nem recorte).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="HTML de saída. Default: <MAPAS_DIR>/<nome>_csv_map.html.",
    )
    parser.add_argument(
        "--cmap",
        default="RdYlGn",
        help="Colormap para o gradiente (default: RdYlGn).",
    )
    parser.add_argument(
        "--vmin",
        type=float,
        help="Valor mínimo fixo do colormap.",
    )
    parser.add_argument(
        "--vmax",
        type=float,
        help="Valor máximo fixo do colormap.",
    )
    parser.add_argument(
        "--opacity",
        type=float,
        default=0.75,
        help="Opacidade do overlay reconstituído (0-1).",
    )
    parser.add_argument(
        "--tiles",
        default="CartoDB positron",
        help="Camada base para o mapa (default: CartoDB positron).",
    )
    parser.add_argument(
        "--tile-attr",
        default="Map tiles by CartoDB, imagery © Esri",
        help="Texto de atribuição exibido no rodapé.",
    )
    parser.add_argument(
        "--no-basemap",
        action="store_true",
        help="Não carrega camada base (tiles).",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.3,
        help="Fator de padding ao recortar usando o GeoJSON (default: 0.3).",
    )
    parser.add_argument(
        "--clip",
        action="store_true",
        default=True,
        help="Ativa recorte do grid pelo GeoJSON (default).",
    )
    parser.add_argument(
        "--no-clip",
        action="store_false",
        dest="clip",
        help="Desativa o recorte pelo GeoJSON.",
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
        help="Zoom mínimo permitido (default: 1).",
    )
    parser.add_argument(
        "--max-zoom",
        type=int,
        default=28,
        help="Zoom máximo permitido (default: 28).",
    )
    parser.add_argument(
        "--max-native-zoom",
        type=int,
        default=19,
        help="Zoom máximo nativo das tiles base (default: 19).",
    )
    return parser.parse_args(argv)


def build_options(args: argparse.Namespace) -> CSVMapOptions:
    tiles = "none" if args.no_basemap else args.tiles
    return CSVMapOptions(
        colormap=args.cmap,
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
    )


def resolve_paths(args: argparse.Namespace, cfg: AppConfig) -> tuple[Path, Path, Optional[Path]]:
    csv_path = args.csv.expanduser().resolve()
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV não encontrado: {csv_path}")

    output_path = (
        args.output.expanduser().resolve()
        if args.output
        else (cfg.MAPAS_DIR / f"{csv_path.stem}_csv_map.html").resolve()
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    geojson_path: Optional[Path] = None
    if not args.no_geojson and args.geojson is not None:
        geojson_path = args.geojson.expanduser().resolve()
        if not geojson_path.exists():
            raise FileNotFoundError(f"GeoJSON não encontrado: {geojson_path}")

    return csv_path, output_path, geojson_path


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = parse_args(argv)
    cfg = AppConfig()
    csv_path, output_path, geojson_path = resolve_paths(args, cfg)

    overlays = [geojson_path] if geojson_path is not None else None
    options = build_options(args)
    renderer = CSVMapRenderer(options)
    prepared = renderer.prepare(csv_path=csv_path, overlays=overlays)

    renderer.render_html(prepared, output_path)
    print(f"Mapa CSV gerado em {output_path}")


if __name__ == "__main__":
    main()
