"""Renderiza true color mais camadas CSV (indices) alternaveis sobre a cena."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from core.engine.renderers import (
    OverlayMapOptions,
    TrueColorOverlayRenderer,
    build_overlay_map as core_build_overlay_map,
)

build_overlay_map = core_build_overlay_map


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--csv-dir", type=Path, required=True, help="Diretorio com os CSVs exportados dos indices.")
    parser.add_argument("--truecolor-red", type=Path, required=True, help="GeoTIFF da banda vermelha (red).")
    parser.add_argument("--truecolor-green", type=Path, required=True, help="GeoTIFF da banda verde (green).")
    parser.add_argument("--truecolor-blue", type=Path, required=True, help="GeoTIFF da banda azul (blue).")
    parser.add_argument("--output", type=Path, default=Path("mapas/overlay_indices.html"), help="Arquivo HTML de saida.")
    parser.add_argument("--indices", nargs="+", help="Lista opcional de CSVs a incluir (nomes sem extensao).")
    parser.add_argument("--geojson", type=Path, nargs="*", help="GeoJSON(s) para overlay e clip.")
    parser.add_argument("--clip", action="store_true", help="Recorta ao(s) poligono(s) informado(s).")
    parser.add_argument("--padding", type=float, default=0.3, help="Padding aplicado ao envelope dos GeoJSONs.")
    parser.add_argument("--tiles", default="CartoDB positron", help="Camada base folium (use 'none' para apenas true color).")
    parser.add_argument("--tile-attr", default=None, help="Atribuicao personalizada do tileset.")
    parser.add_argument("--colormap", default="RdYlGn", help="Colormap para os indices (default: RdYlGn).")
    parser.add_argument("--opacity", type=float, default=0.75, help="Opacidade dos indices (0-1).")
    parser.add_argument("--vmin", type=float, help="Valor minimo fixo para todos os indices.")
    parser.add_argument("--vmax", type=float, help="Valor maximo fixo para todos os indices.")
    parser.add_argument("--upsample", type=float, default=1.0, help="Fator de upsample aplicado aos indices.")
    parser.add_argument("--sharpen", action="store_true", help="Aplica unsharp mask tanto na true color quanto nos indices.")
    parser.add_argument("--sharpen-radius", type=float, default=1.0, help="Raio da unsharp mask.")
    parser.add_argument("--sharpen-amount", type=float, default=1.3, help="Intensidade da unsharp mask.")
    parser.add_argument("--smooth-radius", type=float, default=0.0, help="Suavizacao gaussiana apos o upsample.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    csv_dir = args.csv_dir.expanduser().resolve()
    if not csv_dir.is_dir():
        raise SystemExit(f"Diretorio de CSVs nao encontrado: {csv_dir}")

    overlays = [path.expanduser().resolve() for path in (args.geojson or [])]
    renderer = TrueColorOverlayRenderer(
        OverlayMapOptions(
            tiles=args.tiles,
            tile_attr=args.tile_attr,
            padding_factor=args.padding,
            clip=args.clip,
            colormap=args.colormap,
            opacity=args.opacity,
            vmin=args.vmin,
            vmax=args.vmax,
            upsample=args.upsample,
            sharpen=args.sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=args.smooth_radius,
        )
    )

    output_path = args.output.expanduser().resolve()
    renderer.render(
        csv_dir=csv_dir,
        red_path=args.truecolor_red.expanduser().resolve(),
        green_path=args.truecolor_green.expanduser().resolve(),
        blue_path=args.truecolor_blue.expanduser().resolve(),
        overlays=overlays,
        output_path=output_path,
        indices=args.indices,
    )
    print(f"Mapa com sobreposicoes salvo em {output_path}")


if __name__ == "__main__":
    main()
