"""Gera um dashboard dinamico combinando true color e indices exportados em CSV."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from canasat.rendering import CSVDashboardOptions, CSVDashboardRenderer


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, required=True, help="Diretorio com os CSVs exportados dos indices.")
    parser.add_argument("--truecolor-red", type=Path, required=True, help="GeoTIFF da banda vermelha (red).")
    parser.add_argument("--truecolor-green", type=Path, required=True, help="GeoTIFF da banda verde (green).")
    parser.add_argument("--truecolor-blue", type=Path, required=True, help="GeoTIFF da banda azul (blue).")
    parser.add_argument("--output", type=Path, default=Path("mapas/dashboard_indices.html"), help="Arquivo HTML de saida.")
    parser.add_argument("--colormap", default="RdYlGn", help="Colormap padrao para os indices (default: RdYlGn).")
    parser.add_argument("--opacity", type=float, default=0.75, help="Opacidade dos indices (0-1).")
    parser.add_argument("--vmin", type=float, help="Valor minimo global.")
    parser.add_argument("--vmax", type=float, help="Valor maximo global.")
    parser.add_argument("--geojson", type=Path, nargs="*", help="GeoJSON(s) para overlay/clip.")
    parser.add_argument("--padding", type=float, default=0.3, help="Padding aplicado ao envelope do GeoJSON.")
    parser.add_argument("--clip", action="store_true", help="Recorta ao poligono do GeoJSON.")
    parser.add_argument("--tiles", default="CartoDB positron", help="Camada base (use 'none' para offline).")
    parser.add_argument("--tile-attr", default=None, help="Atribuicao personalizada do tileset.")
    parser.add_argument("--sharpen", action="store_true", help="Aplica unsharp mask aos indices e true color.")
    parser.add_argument("--sharpen-radius", type=float, default=1.0, help="Raio da unsharp mask.")
    parser.add_argument("--sharpen-amount", type=float, default=1.3, help="Intensidade da unsharp mask.")
    parser.add_argument("--upsample", type=float, default=1.0, help="Fator de upsample dos indices.")
    parser.add_argument("--smooth-radius", type=float, default=0.0, help="Raio de suavizacao apos o upsample.")
    parser.add_argument(
        "--stretch",
        type=float,
        nargs=2,
        default=(2.0, 98.0),
        metavar=("LOWER", "UPPER"),
        help="Percentis usados no stretch da true color (default: 2 98).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    options = CSVDashboardOptions(
        colormap=args.colormap,
        opacity=args.opacity,
        vmin=args.vmin,
        vmax=args.vmax,
        tiles=args.tiles,
        tile_attr=args.tile_attr,
        padding_factor=args.padding,
        clip=args.clip,
        sharpen=args.sharpen,
        sharpen_radius=args.sharpen_radius,
        sharpen_amount=args.sharpen_amount,
        upsample=args.upsample,
        smooth_radius=args.smooth_radius,
        stretch_lower=args.stretch[0],
        stretch_upper=args.stretch[1],
    )
    renderer = CSVDashboardRenderer(options)
    output = renderer.render(
        csv_dir=args.csv_dir.expanduser().resolve(),
        red_path=args.truecolor_red.expanduser().resolve(),
        green_path=args.truecolor_green.expanduser().resolve(),
        blue_path=args.truecolor_blue.expanduser().resolve(),
        overlays=[path.expanduser().resolve() for path in (args.geojson or [])],
        output_path=args.output.expanduser().resolve(),
    )
    print(f"Dashboard salvo em {output}")


if __name__ == "__main__":
    main()

