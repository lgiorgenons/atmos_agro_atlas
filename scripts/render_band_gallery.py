"""Generate an HTML gallery showing all Sentinel-2 bands for a processed product."""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional, Sequence

from canasat.rendering import BandGalleryOptions, BandGalleryRenderer, build_gallery as core_build_gallery

build_gallery = core_build_gallery


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product-dir", type=Path, required=True, help="Diretorio contendo as bandas (GeoTIFF).")
    parser.add_argument("--output", type=Path, default=Path("mapas/band_gallery.html"), help="Arquivo HTML de saida.")
    parser.add_argument("--geojson", type=Path, help="GeoJSON opcional para recorte/overlay.")
    parser.add_argument(
        "--stretch",
        type=float,
        nargs=2,
        default=(2.0, 98.0),
        metavar=("LOWER", "UPPER"),
        help="Percentis usados para o stretch de contraste (default: 2 98).",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    options = BandGalleryOptions(stretch_percentiles=tuple(args.stretch))
    renderer = BandGalleryRenderer(options)
    output = renderer.render(
        product_dir=args.product_dir.expanduser().resolve(),
        output_html=args.output.expanduser().resolve(),
        geojson_path=args.geojson.expanduser().resolve() if args.geojson else None,
    )
    print(f"Galeria de bandas salva em {output}")


if __name__ == "__main__":
    main()

