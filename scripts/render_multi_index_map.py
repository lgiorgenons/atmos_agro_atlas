"""Gera um mapa interativo com múltiplas camadas de índices.

Este wrapper delega para o core (`core.engine.renderers`) que concentra a lógica de
processamento e renderização. Assim a API/CLI continuam finas enquanto o core
pode ser reutilizado por outros consumidores (workers, notebooks, etc.).
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Iterable, Optional, Sequence

from core.engine.renderers import MultiIndexMapOptions, MultiIndexMapRenderer

DEFAULT_CMAP = "RdYlGn"


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, nargs="+", required=True, help="Arquivos GeoTIFF dos índices.")
    parser.add_argument("--output", type=Path, default=Path("mapas/compare_indices.html"), help="HTML de saída.")
    parser.add_argument("--colormap", default=DEFAULT_CMAP, help="Nome do colormap Matplotlib (default: RdYlGn).")
    parser.add_argument("--vmin", type=float, help="Valor mínimo para o Stretch (opcional).")
    parser.add_argument("--vmax", type=float, help="Valor máximo para o Stretch (opcional).")
    parser.add_argument("--opacity", type=float, default=0.75, help="Opacidade da camada raster (0-1).")
    parser.add_argument("--geojson", type=Path, nargs="*", help="Arquivos GeoJSON adicionais para sobrepor.")
    parser.add_argument("--tiles", default="CartoDB positron", help="Camada base do folium (ou 'none').")
    parser.add_argument("--tile-attr", default=None, help="Atribuição para a camada base.")
    parser.add_argument("--padding", type=float, default=0.3, help="Fator de expansão do envelope do GeoJSON.")
    parser.add_argument("--clip", action="store_true", help="Recorta os rasters ao(s) polígono(s) do(s) GeoJSON(s).")
    parser.add_argument("--upsample", type=float, default=1.0, help="Fator de upsample para suavizar pixels (ex.: 4..12).")
    parser.add_argument("--sharpen", action="store_true", help="Aplica filtro de nitidez (unsharp mask).")
    parser.add_argument("--sharpen-radius", type=float, default=1.0, help="Raio (sigma) usado na gaussiana do filtro.")
    parser.add_argument("--sharpen-amount", type=float, default=1.2, help="Intensidade do realce de nitidez.")
    parser.add_argument("--smooth-radius", type=float, default=0.0, help="Suavização gaussiana após o upsample.")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    options = MultiIndexMapOptions(
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
    renderer = MultiIndexMapRenderer(options)
    output = renderer.render(
        index_paths=[p.expanduser().resolve() for p in args.index],
        output_path=args.output.expanduser().resolve(),
        overlays=[path.expanduser().resolve() for path in (args.geojson or [])],
    )
    print(f"Mapa de comparação salvo em {output}")


if __name__ == "__main__":
    main()
