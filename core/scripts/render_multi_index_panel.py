from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, List, Optional

from core.engine.renderers import IndexMapOptions, IndexMapRenderer, MultiIndexMapOptions, MultiIndexMapRenderer


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Gera um painel interativo com múltiplos índices e exporta CSVs para cada um."
    )
    parser.add_argument(
        "--product-dir",
        type=Path,
        required=True,
        help="Diretório do produto processado (ex.: data/processed/<produto>).",
    )
    parser.add_argument(
        "--geojson",
        type=Path,
        default=Path("dados/map.geojson"),
        help="GeoJSON com os talhões ou propriedade.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("mapas/indices_panel.html"),
        help="Arquivo HTML de saída.",
    )
    parser.add_argument(
        "--export-csv-dir",
        type=Path,
        default=Path("tabelas/indices_panel"),
        help="Diretório onde os CSVs serão salvos.",
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        help="Lista de índices (ex.: ndvi ndmi). Se omitido, usa todos os arquivos em indices/.",
    )
    parser.add_argument("--tiles", default="CartoDB positron", help="Basemap utilizado no painel.")
    parser.add_argument("--upsample", type=float, default=8.0, help="Fator de upsample dos rasters.")
    parser.add_argument("--smooth-radius", type=float, default=1.0, help="Suavização gaussiana.")
    parser.add_argument("--no-sharpen", action="store_true", help="Desativa filtro de nitidez.")
    parser.add_argument("--clip", action="store_true", help="Recorta os rasters pelo GeoJSON.")
    return parser.parse_args()


def gather_index_paths(product_dir: Path, requested: Optional[Iterable[str]]) -> List[Path]:
    indices_dir = product_dir / "indices"
    if not indices_dir.exists():
        raise FileNotFoundError(f"Diretório de índices não encontrado: {indices_dir}")
    paths = sorted(indices_dir.glob("*.tif"))
    if requested:
        wanted = {name.lower() for name in requested}
        paths = [path for path in paths if path.stem.lower() in wanted]
    if not paths:
        raise RuntimeError("Nenhum arquivo de índice encontrado para gerar o painel.")
    return paths


def export_csvs(
    index_paths: Iterable[Path],
    renderer: IndexMapRenderer,
    overlays: Optional[Iterable[Path]],
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for path in index_paths:
        prepared = renderer.prepare(index_path=path, overlays=overlays)
        target = output_dir / f"{path.stem}.csv"
        renderer.export_csv(prepared, target)


def main() -> None:
    args = parse_args()
    index_paths = gather_index_paths(args.product_dir, args.indices)
    overlays = [args.geojson] if args.geojson else None

    panel_renderer = MultiIndexMapRenderer(
        MultiIndexMapOptions(
            tiles=args.tiles,
            tile_attr="Map data",
            padding_factor=0.3,
            clip=args.clip,
            upsample=max(args.upsample, 1.0),
            smooth_radius=max(args.smooth_radius, 0.0),
            sharpen=not args.no_sharpen,
            sharpen_radius=1.2,
            sharpen_amount=1.5,
            enable_panel=True,
        )
    )
    panel_renderer.render(
        index_paths=index_paths,
        output_path=args.output,
        overlays=overlays,
    )

    csv_renderer = IndexMapRenderer(
        IndexMapOptions(
            tiles="none",
            padding_factor=0.3,
            clip=args.clip,
            upsample=max(args.upsample, 1.0),
            smooth_radius=max(args.smooth_radius, 0.0),
            sharpen=not args.no_sharpen,
            sharpen_radius=1.2,
            sharpen_amount=1.5,
        )
    )
    export_csvs(index_paths, csv_renderer, overlays, args.export_csv_dir)
    print(f"Painel gerado em {args.output}")
    print(f"CSVs exportados para {args.export_csv_dir}")


if __name__ == "__main__":
    main()
