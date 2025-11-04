"""Renderiza um mapa interativo com composicao RGB (true color) a partir de bandas Sentinel-2.

CLI fina que delega o trabalho ao core OO (`canasat.rendering.TrueColorRenderer`).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from canasat.rendering import TrueColorOptions, TrueColorRenderer, build_truecolor_map as core_build_truecolor_map

# Compatibilidade com importacoes legadas
build_truecolor_map = core_build_truecolor_map


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--red", type=Path, required=True, help="Caminho para banda vermelha (B04).")
    parser.add_argument("--green", type=Path, required=True, help="Caminho para banda verde (B03).")
    parser.add_argument("--blue", type=Path, required=True, help="Caminho para banda azul (B02).")
    parser.add_argument("--output", type=Path, default=Path("mapas/truecolor.html"), help="Arquivo HTML de saida.")
    parser.add_argument("--geojson", type=Path, nargs="*", help="Arquivos GeoJSON para sobrepor no mapa.")
    parser.add_argument("--tiles", default="CartoDB positron", help="Camada base do folium (ou 'none').")
    parser.add_argument("--tile-attr", default=None, help="Atribuicao para a camada base.")
    parser.add_argument("--padding", type=float, default=0.3, help="Fator de expansao do envelope do GeoJSON.")
    parser.add_argument("--sharpen", action="store_true", help="Aplica unsharp mask para realcar detalhes.")
    parser.add_argument("--sharpen-radius", type=float, default=1.0, help="Raio (sigma) da gaussiana na nitidez.")
    parser.add_argument("--sharpen-amount", type=float, default=1.2, help="Intensidade do realce de nitidez.")
    parser.add_argument("--stretch-lower", type=float, default=2.0, help="Percentil inferior para stretch (default: 2).")
    parser.add_argument("--stretch-upper", type=float, default=98.0, help="Percentil superior para stretch (default: 98).")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    overlays = [path.expanduser().resolve() for path in (args.geojson or [])]

    options = TrueColorOptions(
        tiles=args.tiles,
        tile_attr=args.tile_attr,
        padding_factor=args.padding,
        sharpen=args.sharpen,
        sharpen_radius=args.sharpen_radius,
        sharpen_amount=args.sharpen_amount,
        stretch_lower=args.stretch_lower,
        stretch_upper=args.stretch_upper,
    )
    renderer = TrueColorRenderer(options)

    data = renderer.prepare(
        red_path=args.red.expanduser().resolve(),
        green_path=args.green.expanduser().resolve(),
        blue_path=args.blue.expanduser().resolve(),
        overlays=overlays,
    )
    output = renderer.render_html(data, args.output.expanduser().resolve())
    print(f"Mapa true color salvo em {output}")


if __name__ == "__main__":
    main()

