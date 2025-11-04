"""Generate a side-by-side map comparing true-color imagery with a spectral index."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from canasat.rendering import (
    ComparisonMapOptions,
    ComparisonMapRenderer,
    build_comparison_map as core_build_comparison_map,
)

build_comparison_map = core_build_comparison_map


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True, help="GeoTIFF com o indice (NDVI, NDRE, etc.).")
    parser.add_argument("--output", type=Path, default=Path("mapas/comparativo.html"), help="Arquivo HTML de saida.")
    parser.add_argument("--geojson", type=Path, nargs="*", default=[], help="Arquivos GeoJSON para destacar no mapa.")
    parser.add_argument("--colormap", default="RdYlGn", help="Colormap Matplotlib para renderizar o indice.")
    parser.add_argument("--opacity", type=float, default=0.75, help="Opacidade aplicada ao indice (0-1).")
    parser.add_argument("--vmin", type=float, help="Valor minimo para normalizacao.")
    parser.add_argument("--vmax", type=float, help="Valor maximo para normalizacao.")
    parser.add_argument("--sharpen", action="store_true", help="Aplica unsharp mask ao raster do indice.")
    parser.add_argument("--sharpen-radius", type=float, default=1.2, help="Raio (sigma) da unsharp mask.")
    parser.add_argument("--sharpen-amount", type=float, default=1.5, help="Intensidade do realce de nitidez.")
    parser.add_argument("--tiles", default="OpenStreetMap", help="Tileset base (OpenStreetMap, Stamen Terrain, etc.).")
    parser.add_argument("--tile-attr", default=None, help="Atribuicao do tileset base.")
    parser.add_argument("--max-zoom", type=int, default=19, help="Zoom maximo permitido no mapa.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    renderer = ComparisonMapRenderer(
        ComparisonMapOptions(
            colormap=args.colormap,
            opacity=args.opacity,
            vmin=args.vmin,
            vmax=args.vmax,
            sharpen=args.sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            tiles=args.tiles,
            tile_attr=args.tile_attr,
            max_zoom=args.max_zoom,
        )
    )
    output = renderer.render(
        index_path=args.index.expanduser().resolve(),
        output_path=args.output.expanduser().resolve(),
        overlays=[path.expanduser().resolve() for path in args.geojson],
    )
    print(f"Mapa comparativo salvo em {output}")


if __name__ == "__main__":
    main()

