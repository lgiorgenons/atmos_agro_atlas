"""Run the entire Sentinel-2 workflow with a single command.

Steps performed:
1. download (or reuse) a Sentinel-2 Level-2A product;
2. extract the spectral bands and compute vegetation indices;
3. export every index to CSV clipped to the AOI; and
4. render the same HTML maps described in the README.

The goal is to keep the manual commands documented while providing a convenient
wrapper for automation and scheduled executions.
"""
from __future__ import annotations

import argparse
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from satellite_pipeline import (
    INDEX_SPECS,
    AreaOfInterest,
    analyse_scene,
    authenticate_from_env,
    create_dataspace_session,
    download_product,
    extract_bands_from_safe,
    query_latest_product,
    _infer_product_name,
)

# OO orchestration (optional, used when available)
try:
    from canasat.workflow.orchestrator import WorkflowService
    from canasat.config.settings import AppConfig
    _HAS_CANASAT = True
except Exception:  # pragma: no cover - optional during migration
    _HAS_CANASAT = False

from render_index_map import (
    build_map as build_index_map,
    export_csv,
    prepare_map_data,
)
try:
    from canasat.rendering import build_multi_map, build_truecolor_map  # type: ignore
except Exception:  # pragma: no cover - fallback durante migração
    from render_multi_index_map import build_multi_map  # type: ignore
    from render_truecolor_map import build_truecolor_map  # type: ignore
from render_csv_map import (
    _prepare_from_csv,
    build_map as build_csv_map,
)
from render_truecolor_overlay_map import build_overlay_map

LOGGER = logging.getLogger(__name__)

DEFAULT_PRIMARY_INDICES = ["ndvi", "ndre", "ndmi", "ndwi", "evi"]
DEFAULT_OVERLAY_INDICES = ["ndvi", "ndmi", "ndre", "ndwi"]


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)

    date_group = parser.add_mutually_exclusive_group(required=True)
    date_group.add_argument(
        "--date",
        help="Single acquisition date in YYYY-MM-DD format (applies to start and end).",
    )
    date_group.add_argument(
        "--date-range",
        nargs=2,
        metavar=("START", "END"),
        help="Search range in YYYY-MM-DD format (inclusive).",
    )

    parser.add_argument(
        "--geojson",
        type=Path,
        default=Path("dados/map.geojson"),
        help="AOI polygon in GeoJSON format (default: dados/map.geojson).",
    )
    parser.add_argument(
        "--cloud",
        type=int,
        nargs=2,
        default=(0, 30),
        metavar=("MIN", "MAX"),
        help="Acceptable cloud cover percentage range (default: 0 30).",
    )
    parser.add_argument(
        "--download-dir",
        type=Path,
        default=Path("data/raw"),
        help="Directory used to store the downloaded SAFE product (default: data/raw).",
    )
    parser.add_argument(
        "--workdir",
        type=Path,
        default=Path("data/processed"),
        help="Directory where bands and indices are stored (default: data/processed).",
    )
    parser.add_argument(
        "--maps-dir",
        type=Path,
        default=Path("mapas"),
        help="Output folder for HTML maps (default: mapas).",
    )
    parser.add_argument(
        "--tables-dir",
        type=Path,
        default=Path("tabelas"),
        help="Output folder for CSV tables (default: tabelas).",
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        choices=sorted(INDEX_SPECS.keys()),
        help="Subset of indices to compute (default: all available).",
    )
    parser.add_argument(
        "--primary-indices",
        nargs="+",
        default=DEFAULT_PRIMARY_INDICES,
        help="Indices highlighted in compare_indices.html (default: %(default)s).",
    )
    parser.add_argument(
        "--overlay-indices",
        nargs="+",
        default=DEFAULT_OVERLAY_INDICES,
        help="Indices used in the optional true color overlay (default: %(default)s).",
    )
    parser.add_argument(
        "--upsample",
        type=float,
        default=12.0,
        help="Upsample factor applied before smoothing (default: 12).",
    )
    parser.add_argument(
        "--smooth-radius",
        type=float,
        default=1.0,
        help="Gaussian smooth radius after upsample (default: 1.0).",
    )
    parser.add_argument(
        "--sharpen-radius",
        type=float,
        default=1.2,
        help="Sigma used by the unsharp mask (default: 1.2).",
    )
    parser.add_argument(
        "--sharpen-amount",
        type=float,
        default=1.5,
        help="Unsharp mask amount (default: 1.5).",
    )
    parser.add_argument(
        "--no-sharpen",
        action="store_true",
        help="Disable the unsharp mask before exporting rasters and CSVs.",
    )
    parser.add_argument(
        "--padding",
        type=float,
        default=0.3,
        help="Padding applied around the AOI bounds (default: 0.3).",
    )
    parser.add_argument("--tiles", default="CartoDB positron", help="Folium base map (default: CartoDB positron).")
    parser.add_argument("--tile-attr", default=None, help="Custom attribution string for the tileset.")
    parser.add_argument("--colormap", default="RdYlGn", help="Matplotlib colormap name (default: RdYlGn).")
    parser.add_argument("--opacity", type=float, default=0.75, help="Raster layer opacity (default: 0.75).")
    parser.add_argument("--vmin", type=float, help="Optional fixed minimum for colour stretch.")
    parser.add_argument("--vmax", type=float, help="Optional fixed maximum for colour stretch.")
    parser.add_argument(
        "--generate-overlay",
        action="store_true",
        help="Render overlay_indices.html (large file because of the true color backdrop).",
    )
    parser.add_argument(
        "--safe-path",
        type=Path,
        help="Existing SAFE (zip or directory) to reuse instead of downloading again.",
    )
    parser.add_argument("--username", help="Copernicus username (overrides SENTINEL_USERNAME).")
    parser.add_argument("--password", help="Copernicus password (overrides SENTINEL_PASSWORD).")
    parser.add_argument("--api-url", help="Override SENTINEL_API_URL.")
    parser.add_argument("--token-url", help="Override SENTINEL_TOKEN_URL.")
    parser.add_argument("--client-id", help="Override SENTINEL_CLIENT_ID.")
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )
    return parser.parse_args(argv)


def _ensure_dir(path: Path) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_indices(requested: Optional[Iterable[str]]) -> List[str]:
    if requested is None:
        return sorted(INDEX_SPECS.keys())
    unique = list(dict.fromkeys(requested))
    missing = [name for name in unique if name not in INDEX_SPECS]
    if missing:
        raise SystemExit(f"Unsupported indices requested: {', '.join(missing)}")
    return unique


def _select_available(names: Iterable[str], available: Dict[str, Path]) -> List[str]:
    selected: List[str] = []
    for name in names:
        if name in available:
            selected.append(name)
        else:
            LOGGER.warning("Index %s was not generated and will be skipped.", name)
    return selected


def _resolve_dates(args: argparse.Namespace) -> Tuple[str, str]:
    if args.date:
        return args.date, args.date
    start, end = args.date_range
    return start, end


def _prepare_overlay_list(geojson: Optional[Path]) -> List[Path]:
    return [geojson] if geojson is not None else []


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = _parse_args(argv)
    logging.basicConfig(level=args.log_level, format="%(levelname)s %(message)s")

    start_date, end_date = _resolve_dates(args)
    overlays = _prepare_overlay_list(args.geojson.expanduser().resolve())
    upsample = max(args.upsample, 1.0)
    smooth_radius = max(args.smooth_radius, 0.0)
    apply_sharpen = not args.no_sharpen

    download_dir = _ensure_dir(args.download_dir.expanduser().resolve())
    workdir = _ensure_dir(args.workdir.expanduser().resolve())
    maps_dir = _ensure_dir(args.maps_dir.expanduser().resolve())
    tables_dir = _ensure_dir(args.tables_dir.expanduser().resolve())

    selected_indices = _normalise_indices(args.indices)
    primary_indices = _select_available(args.primary_indices, {name: Path() for name in selected_indices})
    overlay_indices = _select_available(args.overlay_indices, {name: Path() for name in selected_indices})

    product_path: Path
    product_title: str
    bands: Dict[str, Path]
    outputs: Dict[str, Path]

    if args.safe_path:
        product_path = args.safe_path.expanduser().resolve()
        if not product_path.exists():
            raise SystemExit(f"SAFE not found: {product_path}")
        product_title = _infer_product_name(product_path)
        LOGGER.info("Using existing SAFE: %s", product_title)
        bands = extract_bands_from_safe(product_path, workdir / product_title)
        outputs = analyse_scene(bands, workdir / product_title / "indices", indices=selected_indices)
    else:
        if _HAS_CANASAT:
            # Preferir a orquestração OO quando disponível
            cfg = AppConfig(
                DATA_RAW_DIR=download_dir,
                DATA_PROCESSED_DIR=workdir,
                MAPAS_DIR=maps_dir,
                TABELAS_DIR=tables_dir,
                SENTINEL_USERNAME=args.username,
                SENTINEL_PASSWORD=args.password,
                SENTINEL_API_URL=(args.api_url or None),
                SENTINEL_TOKEN_URL=(args.token_url or None),
                SENTINEL_CLIENT_ID=(args.client_id or None) or "cdse-public",
            )
            svc = WorkflowService(cfg)
            from datetime import datetime as _dt

            start_dt = _dt.fromisoformat(start_date).date()
            end_dt = _dt.fromisoformat(end_date).date()

            LOGGER.info("Searching Sentinel-2 products between %s and %s (OO)", start_date, end_date)
            result = svc.run_date_range(
                start=start_dt,
                end=end_dt,
                aoi_geojson=args.geojson.expanduser().resolve(),
                cloud=tuple(args.cloud),
                indices=selected_indices,
                upsample=upsample,
                smooth_radius=smooth_radius,
                sharpen=apply_sharpen,
                sharpen_radius=args.sharpen_radius,
                sharpen_amount=args.sharpen_amount,
                tiles=args.tiles,
                padding=args.padding,
            )
            product_title = result.product_title
            bands = result.bands
            outputs = result.indices
        else:
            # Caminho legado (sem OO)
            config = authenticate_from_env(
                username=args.username,
                password=args.password,
                api_url=args.api_url,
                token_url=args.token_url,
                client_id=args.client_id,
            )
            area = AreaOfInterest.from_geojson(args.geojson)

            LOGGER.info("Searching Sentinel-2 products between %s and %s", start_date, end_date)
            session = create_dataspace_session(config)
            try:
                product = query_latest_product(session, config, area, start_date, end_date, tuple(args.cloud))
                if not product:
                    raise SystemExit("No Sentinel-2 product matched the provided filters.")

                product_name = product.get("Name") or product.get("Id") or "unnamed_product"
                archive_name = product_name if product_name.endswith(".zip") else f"{product_name}.zip"
                cached_zip = download_dir / archive_name
                cached_dir = download_dir / product_name

                if cached_zip.exists():
                    product_path = cached_zip
                    LOGGER.info("Reusing cached SAFE archive at %s", product_path)
                elif cached_dir.exists():
                    product_path = cached_dir
                    LOGGER.info("Reusing cached SAFE directory at %s", product_path)
                else:
                    LOGGER.info("Downloading product %s", product_name)
                    product_path = download_product(session, product, download_dir, config.api_url)
            finally:
                session.close()

            product_title = _infer_product_name(product_path, fallback=product_name)
            LOGGER.info("Extracting spectral bands for %s", product_title)
            bands = extract_bands_from_safe(product_path, workdir / product_title)

            indices_dir = workdir / product_title / "indices"
            cached_outputs: Dict[str, Path] = {}
            if indices_dir.exists():
                for name in selected_indices:
                    candidate = indices_dir / f"{name}.tif"
                    if candidate.exists():
                        cached_outputs[name] = candidate

            if len(cached_outputs) == len(selected_indices):
                LOGGER.info("Reusing existing indices for %s", product_title)
                outputs = cached_outputs
            else:
                LOGGER.info("Computing spectral indices: %s", ", ".join(selected_indices))
                outputs = analyse_scene(bands, indices_dir, indices=selected_indices)

    LOGGER.info("Total indices generated: %d", len(outputs))

    available_primary = _select_available(primary_indices, outputs)
    available_overlay = _select_available(overlay_indices, outputs)

    if "ndvi" in outputs:
        LOGGER.info("Rendering mapas/ndvi.html")
        prepared_ndvi = prepare_map_data(
            outputs["ndvi"],
            overlays=overlays,
            padding_factor=args.padding,
            clip=True,
            upsample=upsample,
            sharpen=apply_sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=smooth_radius,
        )
        build_index_map(
            prepared_ndvi,
            maps_dir / "ndvi.html",
            cmap_name=args.colormap,
            vmin=args.vmin,
            vmax=args.vmax,
            opacity=args.opacity,
            tiles=args.tiles,
            tile_attr=args.tile_attr,
        )

    if len(available_primary) >= 2:
        LOGGER.info("Rendering mapas/compare_indices.html")
        build_multi_map(
            index_paths=[outputs[name] for name in available_primary],
            output_path=maps_dir / "compare_indices.html",
            cmap_name=args.colormap,
            vmin=args.vmin,
            vmax=args.vmax,
            opacity=args.opacity,
            overlays=overlays,
            tiles=args.tiles,
            tile_attr=args.tile_attr,
            padding_factor=args.padding,
            clip=True,
            upsample=upsample,
            sharpen=apply_sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=smooth_radius,
        )

    if outputs:
        LOGGER.info("Rendering mapas/compare_indices_all.html")
        build_multi_map(
            index_paths=[path for _, path in sorted(outputs.items())],
            output_path=maps_dir / "compare_indices_all.html",
            cmap_name=args.colormap,
            vmin=args.vmin,
            vmax=args.vmax,
            opacity=args.opacity,
            overlays=overlays,
            tiles=args.tiles,
            tile_attr=args.tile_attr,
            padding_factor=args.padding,
            clip=True,
            upsample=upsample,
            sharpen=apply_sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=smooth_radius,
        )

    if {"red", "green", "blue"} <= bands.keys():
        LOGGER.info("Rendering mapas/truecolor.html")
        build_truecolor_map(
            red_path=bands["red"],
            green_path=bands["green"],
            blue_path=bands["blue"],
            output_path=maps_dir / "truecolor.html",
            overlays=overlays,
            tiles=args.tiles,
            tile_attr=args.tile_attr,
            padding_factor=args.padding,
            sharpen=apply_sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
        )
    else:
        LOGGER.warning("RGB bands were not found; skipping true color map.")

    csv_paths: Dict[str, Path] = {}
    LOGGER.info("Exporting indices to CSV inside %s", tables_dir)
    for name, index_path in outputs.items():
        prepared = prepare_map_data(
            index_path,
            overlays=overlays,
            padding_factor=args.padding,
            clip=True,
            upsample=upsample,
            sharpen=apply_sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=smooth_radius,
        )
        csv_path = tables_dir / f"{name}.csv"
        export_csv(prepared, csv_path)
        csv_paths[name] = csv_path

    if "ndvi" in csv_paths:
        LOGGER.info("Rendering mapas/ndvi_from_csv.html")
        prepared_csv = _prepare_from_csv(
            csv_paths["ndvi"],
            overlays,
            padding_factor=args.padding,
            clip=True,
            upsample=upsample,
            sharpen=apply_sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=smooth_radius,
        )
        build_csv_map(
            prepared=prepared_csv,
            output_path=maps_dir / "ndvi_from_csv.html",
            cmap_name=args.colormap,
            vmin=args.vmin,
            vmax=args.vmax,
            opacity=args.opacity,
            tiles=args.tiles,
            tile_attr=args.tile_attr,
        )

    if args.generate_overlay and {"red", "green", "blue"} <= bands.keys():
        available_overlay = _select_available(available_overlay, csv_paths)
        LOGGER.info("Rendering mapas/overlay_indices.html (large file)")
        build_overlay_map(
            csv_dir=tables_dir,
            red_path=bands["red"],
            green_path=bands["green"],
            blue_path=bands["blue"],
            overlays=overlays,
            clip=True,
            padding=args.padding,
            tiles=args.tiles,
            tile_attr=args.tile_attr,
            colormap=args.colormap,
            opacity=args.opacity,
            vmin=args.vmin,
            vmax=args.vmax,
            upsample=upsample,
            sharpen=apply_sharpen,
            sharpen_radius=args.sharpen_radius,
            sharpen_amount=args.sharpen_amount,
            smooth_radius=smooth_radius,
            indices=available_overlay if available_overlay else None,
        )
    elif args.generate_overlay:
        LOGGER.warning("Cannot build overlay_indices.html because RGB bands are missing.")

    LOGGER.info(
        "Workflow finished for %s at %s UTC.",
        product_title,
        datetime.utcnow().strftime("%Y-%m-%d %H:%M"),
    )


if __name__ == "__main__":
    main()
