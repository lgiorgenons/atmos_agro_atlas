"""Renderiza um mapa interativo a partir de um CSV (lon, lat, value) exportado do pipeline.

CLI fina que delega ao core (`core.engine.renderers.CSVMapRenderer`).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional, Sequence

from core.engine.renderers import (
    CSVMapOptions,
    CSVMapRenderer,
    PreparedRaster,
    build_csv_map as core_build_csv_map,
)

# Compatibilidade com imports legados
build_map = core_build_csv_map


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv", type=Path, required=True, help="Arquivo CSV com colunas longitude, latitude e value.")
    parser.add_argument("--output", type=Path, default=Path("mapa_csv.html"), help="HTML de saida.")
    parser.add_argument("--colormap", default="RdYlGn", help="Colormap Matplotlib (default: RdYlGn).")
    parser.add_argument("--vmin", type=float, help="Valor minimo para o stretch.")
    parser.add_argument("--vmax", type=float, help="Valor maximo para o stretch.")
    parser.add_argument("--opacity", type=float, default=0.75, help="Opacidade da camada (0-1).")
    parser.add_argument("--geojson", type=Path, nargs="*", help="GeoJSON(s) para overlay e recorte.")
    parser.add_argument("--tiles", default="CartoDB positron", help="Camada base (use 'none' para modo offline).")
    parser.add_argument("--tile-attr", default=None, help="Atribuicao personalizada da camada base.")
    parser.add_argument("--padding", type=float, default=0.3, help="Padding aplicado ao envelope do GeoJSON.")
    parser.add_argument("--clip", action="store_true", help="Recorta a malha ao(s) poligono(s) do(s) GeoJSON(s).")
    parser.add_argument("--sharpen", action="store_true", help="Aplica unsharp mask antes da renderizacao.")
    parser.add_argument("--sharpen-radius", type=float, default=1.0, help="Raio (sigma) da unsharp mask.")
    parser.add_argument("--sharpen-amount", type=float, default=1.3, help="Intensidade da unsharp mask.")
    parser.add_argument("--upsample", type=float, default=1.0, help="Fator de upsample para suavizar pixels.")
    parser.add_argument("--smooth-radius", type=float, default=0.0, help="Raio da suavizacao gaussiana apos upsample.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    overlays = [path.expanduser().resolve() for path in (args.geojson or [])]

    options = CSVMapOptions(
        colormap=args.colormap,
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
    renderer = CSVMapRenderer(options)

    prepared = renderer.prepare(csv_path=args.csv.expanduser().resolve(), overlays=overlays)
    output = renderer.render_html(prepared, args.output.expanduser().resolve())
    print(f"Mapa CSV salvo em {output}")


def _prepare_from_csv(
    csv_path: Path,
    overlay_paths: Iterable[Path],
    *,
    padding_factor: float,
    clip: bool,
    upsample: float,
    sharpen: bool,
    sharpen_radius: float,
    sharpen_amount: float,
    smooth_radius: float,
) -> PreparedRaster:
    renderer = CSVMapRenderer(
        CSVMapOptions(
            padding_factor=padding_factor,
            clip=clip,
            upsample=upsample,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
            smooth_radius=smooth_radius,
        )
    )
    return renderer.prepare(csv_path=csv_path, overlays=overlay_paths)


if __name__ == "__main__":
    main()
