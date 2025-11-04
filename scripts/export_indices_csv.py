"""Exporta todos os GeoTIFF de indices de um diretorio para CSV.

Os valores sao convertidos para WGS84 (lon, lat) e salvos com um arquivo
CSV por indice para facilitar integracoes posteriores.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from core.engine.renderers import IndexMapOptions, IndexMapRenderer


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--indices-dir",
        type=Path,
        required=True,
        help="Diretorio com os GeoTIFF dos indices (ex.: data/processed/.../indices).",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("tabelas"),
        help="Pasta onde os CSV serao gravados (default: tabelas).",
    )
    parser.add_argument("--geojson", type=Path, nargs="*", help="GeoJSON(s) para clipping e exportacao das bordas.")
    parser.add_argument(
        "--padding",
        type=float,
        default=0.3,
        help="Fator de expansao do envelope do GeoJSON quando clip=True (default: 0.3).",
    )
    parser.add_argument("--clip", action="store_true", help="Recorta os rasters ao(s) poligono(s) do(s) GeoJSON(s).")
    parser.add_argument("--sharpen", action="store_true", help="Aplica unsharp mask antes da exportacao.")
    parser.add_argument(
        "--sharpen-radius",
        type=float,
        default=1.0,
        help="Raio (sigma) usado na gaussiana da mascara de nitidez (default: 1.0).",
    )
    parser.add_argument(
        "--sharpen-amount",
        type=float,
        default=1.3,
        help="Intensidade da mascara de nitidez (default: 1.3).",
    )
    parser.add_argument("--upsample", type=float, default=1.0, help="Fator de upsample para suavizar pixels (default: 1).")
    parser.add_argument(
        "--smooth-radius",
        type=float,
        default=0.0,
        help="Raio da suavizacao gaussiana apos o upsample (default: 0).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    indices_dir = args.indices_dir.expanduser().resolve()
    output_dir = args.output_dir.expanduser().resolve()
    overlay_paths = [path.expanduser().resolve() for path in (args.geojson or [])]

    if not indices_dir.is_dir():
        raise SystemExit(f"Diretorio de indices nao encontrado: {indices_dir}")

    tif_files = sorted(indices_dir.glob("*.tif"))
    if not tif_files:
        raise SystemExit(f"Nenhum GeoTIFF encontrado em {indices_dir}")

    renderer = IndexMapRenderer(
        IndexMapOptions(
            padding_factor=args.padding,
            clip=args.clip,
            upsample=args.upsample,
            sharpen=args.sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=args.smooth_radius,
        )
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    for tif_path in tif_files:
        prepared = renderer.prepare(index_path=tif_path, overlays=overlay_paths)
        csv_path = output_dir / f"{tif_path.stem}.csv"
        renderer.export_csv(prepared, csv_path)
        print(f"{tif_path.stem}: CSV salvo em {csv_path}")


if __name__ == "__main__":
    main()
