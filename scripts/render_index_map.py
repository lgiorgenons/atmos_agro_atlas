"""Generate an interactive HTML map overlaying a spectral indice GeoTIFF.

Este script mantem a CLI original, mas delega a logica principal para o core
orientado a objetos (`core.engine.renderers.IndexMapRenderer`). As funcoes
`prepare_map_data`, `build_map` e `export_csv` continuam disponiveis para
compatibilidade com outros scripts legados.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from core.engine.renderers import (
    IndexMapOptions,
    IndexMapRenderer,
    PreparedRaster,
    build_map as core_build_map,
    export_csv as core_export_csv,
    prepare_map_data as core_prepare_map_data,
)

DEFAULT_CMAP = "RdYlGn"

# Reexport das funcoes/datatypes para compatibilidade
prepare_map_data = core_prepare_map_data
build_map = core_build_map
export_csv = core_export_csv


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True, help="Arquivo GeoTIFF do indice (NDVI/NDWI/MSI).")
    parser.add_argument("--output", type=Path, default=Path("mapa_indice.html"), help="Arquivo HTML de saida.")
    parser.add_argument("--colormap", default=DEFAULT_CMAP, help="Nome do colormap Matplotlib (default: RdYlGn).")
    parser.add_argument("--vmin", type=float, help="Valor minimo para o Stretch.")
    parser.add_argument("--vmax", type=float, help="Valor maximo para o Stretch.")
    parser.add_argument("--opacity", type=float, default=0.75, help="Opacidade da camada raster (0-1).")
    parser.add_argument("--geojson", type=Path, nargs="*", help="Arquivos GeoJSON adicionais para sobrepor no mapa.")
    parser.add_argument(
        "--tiles",
        default="CartoDB positron",
        help="Camada base do folium (ex.: 'OpenStreetMap'). Use 'none' para modo offline.",
    )
    parser.add_argument(
        "--tile-attr",
        default=None,
        help="Atribuicao personalizada para a camada base (quando aplicavel).",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.3,
        help="Fator de expansao do envelope do GeoJSON (default: 0.3).",
    )
    parser.add_argument("--sharpen", action="store_true", help="Aplica filtro de nitidez (unsharp mask).")
    parser.add_argument("--sharpen-radius", type=float, default=1.0, help="Raio (sigma) usado na gaussiana do filtro.")
    parser.add_argument("--sharpen-amount", type=float, default=1.3, help="Intensidade do realce de nitidez.")
    parser.add_argument("--upsample", type=float, default=1.0, help="Fator de upsample para suavizar pixels (ex.: 4).")
    parser.add_argument("--smooth-radius", type=float, default=0.0, help="Aplica suavizacao gaussiana apos o upsample.")
    parser.add_argument("--clip", action="store_true", help="Recorta o raster ao(s) poligono(s) do(s) GeoJSON(s).")
    parser.add_argument("--csv-output", type=Path, help="Salva os pixels (lon, lat, valor) em um arquivo CSV.")
    parser.add_argument("--no-html", action="store_true", help="Nao gera o HTML; apenas exporta os dados.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    index_path = args.index.expanduser().resolve()
    overlay_paths = [path.expanduser().resolve() for path in (args.geojson or [])]

    options = IndexMapOptions(
        cmap_name=args.colormap,
        vmin=args.vmin,
        vmax=args.vmax,
        opacity=args.opacity,
        tiles=args.tiles,
        tile_attr=args.tile_attr,
        padding_factor=args.padding,
        clip=args.clip,
        upsample=args.upsample,
        sharpen=args.sharpen,
        sharpen_radius=args.sharpen_radius,
        sharpen_amount=args.sharpen_amount,
        smooth_radius=args.smooth_radius,
    )
    renderer = IndexMapRenderer(options)

    prepared: PreparedRaster = renderer.prepare(index_path=index_path, overlays=overlay_paths)

    if args.csv_output:
        csv_output = args.csv_output.expanduser().resolve()
        renderer.export_csv(prepared, csv_output)
        print(f"CSV salvo em {csv_output}")

    if not args.no_html:
        output = renderer.render_html(prepared, args.output.expanduser().resolve())
        print(f"Mapa salvo em {output}")
    elif not args.csv_output:
        print("Nenhuma saida foi gerada. Use --csv-output ou remova --no-html.")


if __name__ == "__main__":
    main()
