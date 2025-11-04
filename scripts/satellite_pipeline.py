"""Tools for downloading and analysing satellite imagery to monitor Sugarcane Wilt Syndrome.

This module provides a small command line utility to:

* query and download Sentinel-2 Level-2A products using the Copernicus Data Space OData API;
* extract the necessary spectral bands; and
* compute vegetation/water stress indicators such as NDVI, NDWI and MSI.

The workflow is inspired by the agronomic discussion available in the
file "AnÃ¡lise Detalhada e Abrangente da SÃ­ndrome da Murcha da Cana-de-AÃ§Ãºcar.md".

The implementation favours composable functions so that the script can be
orchestrated from notebooks or larger data pipelines. For the sake of simplicity
we only download the first product that matches the query criteria. HTTP
requests are issued directly against the OData REST endpoint, while ``rasterio``
and ``numpy`` perform raster handling and analytics.
"""
from __future__ import annotations

import argparse
import logging
import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Iterable, Optional
from urllib.parse import urljoin

import requests
import rasterio

from core.engine.index_calculator import INDEX_SPECS, IndexCalculator
from core.engine.safe_extractor import DEFAULT_SENTINEL_BANDS, SafeExtractor
from core.domain import AreaOfInterest


_LOGGER = logging.getLogger(__name__)


DEFAULT_API_URL = "https://catalogue.dataspace.copernicus.eu/odata/v1/"
DEFAULT_TOKEN_URL = "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
DEFAULT_CLIENT_ID = "cdse-public"
_REQUEST_TIMEOUT = 60


@dataclass
class DownloadConfig:
    """Configuration parameters required to query Sentinel-2 scenes."""

    username: str
    password: str
    api_url: str = DEFAULT_API_URL
    token_url: str = DEFAULT_TOKEN_URL
    client_id: str = DEFAULT_CLIENT_ID


def authenticate_from_env(
    prefix: str = "SENTINEL",
    *,
    username: Optional[str] = None,
    password: Optional[str] = None,
    api_url: Optional[str] = None,
    token_url: Optional[str] = None,
    client_id: Optional[str] = None,
) -> DownloadConfig:
    """Build :class:`DownloadConfig` from CLI arguments and environment variables.

    Parameters
    ----------
    prefix:
        Prefix used to read the credentials, e.g. ``SENTINEL_USERNAME``.

    Returns
    -------
    DownloadConfig
        Credential bundle ready for Copernicus Data Space requests.
    """

    env_username = os.environ.get(f"{prefix}_USERNAME")
    env_password = os.environ.get(f"{prefix}_PASSWORD")
    env_api_url = os.environ.get(f"{prefix}_API_URL")
    env_token_url = os.environ.get(f"{prefix}_TOKEN_URL")
    env_client_id = os.environ.get(f"{prefix}_CLIENT_ID")

    username = username or env_username
    password = password or env_password
    api_url = api_url or env_api_url or DEFAULT_API_URL
    token_url = token_url or env_token_url or DEFAULT_TOKEN_URL
    client_id = client_id or env_client_id or DEFAULT_CLIENT_ID

    if not username or not password:
        raise RuntimeError(
            "Missing Copernicus Data Space credentials. Set the "
            f"{prefix}_USERNAME and {prefix}_PASSWORD environment variables."
        )

    return DownloadConfig(
        username=username,
        password=password,
        api_url=api_url,
        token_url=token_url,
        client_id=client_id,
    )


def _normalise_date(value: str) -> str:
    """Convert date strings to ISO 8601 date (YYYY-MM-DD)."""

    if not value:
        raise ValueError("Date value cannot be empty.")
    upper_value = value.upper()
    if upper_value.startswith("NOW"):
        return value

    for fmt in ("%Y%m%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue

    try:
        parsed = datetime.fromisoformat(value.replace("Z", ""))
    except ValueError as exc:
        raise ValueError(f"Unsupported date format '{value}'. Use YYYY-MM-DD or YYYYMMDD.") from exc
    return parsed.strftime("%Y-%m-%d")


def query_latest_product(
    session: requests.Session,
    config: DownloadConfig,
    area: AreaOfInterest,
    start_date: str,
    end_date: str,
    cloud_cover: Tuple[int, int] = (0, 20),
) -> Optional[Dict]:
    """Query the latest Sentinel-2 product matching the constraints."""

    footprint_wkt = area.to_wkt()
    start_iso = _normalise_date(start_date)
    end_iso = _normalise_date(end_date)
    start_day = datetime.strptime(start_iso, "%Y-%m-%d").date()
    end_day = datetime.strptime(end_iso, "%Y-%m-%d").date()
    start_timestamp = f"{start_day.isoformat()}T00:00:00Z"
    end_timestamp = f"{(end_day + timedelta(days=1)).isoformat()}T00:00:00Z"

    min_cloud, max_cloud = cloud_cover
    cloud_filters: list[str] = []
    if min_cloud > 0:
        cloud_filters.append(
            "Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
            f"and att/OData.CSC.DoubleAttribute/Value ge {float(min_cloud):.2f})"
        )
    cloud_filters.append(
        "Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
        f"and att/OData.CSC.DoubleAttribute/Value le {float(max_cloud):.2f})"
    )
    product_type_filter = (
        "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
        "and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A')"
    )
    filter_parts = [
        "Collection/Name eq 'SENTINEL-2'",
        f"ContentDate/Start ge {start_timestamp}",
        f"ContentDate/Start lt {end_timestamp}",
        f"OData.CSC.Intersects(Footprint, geography'SRID=4326;{footprint_wkt}')",
        product_type_filter,
    ]
    filter_parts.extend(cloud_filters)

    params = {
        "$filter": " and ".join(filter_parts),
        "$orderby": "ContentDate/Start desc",
        "$top": "1",
    }

    products_url = urljoin(config.api_url.rstrip("/") + "/", "Products")
    response = session.get(products_url, params=params, timeout=_REQUEST_TIMEOUT)
    try:
        response.raise_for_status()
    except requests.HTTPError as exc:
        _LOGGER.error("OData query failed: %s", response.text)
        raise exc
    payload = response.json()
    products = payload.get("value", [])
    if not products:
        return None
    return products[0]


def download_product(
    session: requests.Session,
    product: Dict,
    target_dir: Path,
    api_url: str,
) -> Path:
    """Download the provided product into *target_dir* and return the path."""

    target_dir.mkdir(parents=True, exist_ok=True)
    product_id = product.get("Id")
    if not product_id:
        raise RuntimeError("Product payload missing 'Id' field.")

    product_name = product.get("Name") or str(product_id)
    archive_name = product_name if product_name.endswith(".zip") else f"{product_name}.zip"
    download_url = urljoin(api_url.rstrip("/") + "/", f"Products({product_id})/$value")

    target_path = target_dir / archive_name
    current_url = download_url
    for _ in range(5):
        response = session.get(current_url, stream=True, timeout=_REQUEST_TIMEOUT * 10, allow_redirects=False)
        if response.is_redirect:
            location = response.headers.get("Location")
            if not location:
                break
            current_url = urljoin(current_url, location)
            continue
        break
    else:
        raise RuntimeError("Exceeded maximum number of redirects while downloading product.")

    with response:
        if response.status_code >= 400:
            _LOGGER.error("Download request failed (%s): %s", response.status_code, response.text)
            response.raise_for_status()
        with target_path.open("wb") as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file.write(chunk)
    return target_path


def create_dataspace_session(config: DownloadConfig) -> requests.Session:
    """Authenticate against the Copernicus Data Space and return a session."""

    payload = {
        "grant_type": "password",
        "client_id": config.client_id,
        "username": config.username,
        "password": config.password,
    }
    response = requests.post(config.token_url, data=payload, timeout=_REQUEST_TIMEOUT)
    response.raise_for_status()
    token = response.json().get("access_token")
    if not token:
        raise RuntimeError("Failed to obtain access token from Copernicus Data Space.")

    session = requests.Session()
    session.headers.update({"Authorization": f"Bearer {token}"})
    return session


SENTINEL_BANDS = DEFAULT_SENTINEL_BANDS.copy()
_SAFE_EXTRACTOR = SafeExtractor(SENTINEL_BANDS)
_INDEX_CALCULATOR = IndexCalculator(INDEX_SPECS)


def _infer_product_name(product_path: Path, fallback: Optional[str] = None) -> str:
    """Infer a human-friendly product name from a SAFE archive path."""

    stem = product_path.stem
    if stem.endswith(".SAFE"):
        stem = stem[:-5]
    return stem or fallback or product_path.name


def extract_bands_from_safe(safe_archive: Path, destination: Path) -> Dict[str, Path]:
    """Extract relevant bands from a SAFE archive or directory.

    The function is tolerant to either a ``.zip`` file or the already extracted
    SAFE directory. Each requested band is converted to GeoTIFF and stored inside
    ``destination`` with simplified naming, e.g. ``nir.tif``. Bands are
    resampled later on demand so that the calling code can control the reference
    resolution.
    """
    return _SAFE_EXTRACTOR.extract(safe_archive, destination)


def analyse_scene(
    band_paths: Dict[str, Path],
    output_dir: Path,
    indices: Optional[Iterable[str]] = None,
) -> Dict[str, Path]:
    return _INDEX_CALCULATOR.analyse_scene(band_paths=band_paths, output_dir=output_dir, indices=indices)


def _parse_arguments(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--geojson", type=Path, help="Path to AOI GeoJSON polygon (required when downloading)")
    parser.add_argument("--start-date", help="Start date YYYY-MM-DD (required when downloading)")
    parser.add_argument("--end-date", help="End date YYYY-MM-DD (required when downloading)")
    parser.add_argument("--cloud", type=int, nargs=2, default=(0, 20), help="Acceptable cloud cover percentage range")
    parser.add_argument("--download-dir", type=Path, default=Path("data/raw"), help="Directory to store downloaded products")
    parser.add_argument("--workdir", type=Path, default=Path("data/processed"), help="Directory for processed outputs")
    parser.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    parser.add_argument("--username", help="Copernicus Data Space username (overrides SENTINEL_USERNAME env var)")
    parser.add_argument("--password", help="Copernicus Data Space password (overrides SENTINEL_PASSWORD env var)")
    parser.add_argument("--api-url", help=f"OData API base URL (defaults to {DEFAULT_API_URL})")
    parser.add_argument("--token-url", help=f"Copernicus identity token URL (defaults to {DEFAULT_TOKEN_URL})")
    parser.add_argument("--client-id", help=f"OAuth client id (defaults to {DEFAULT_CLIENT_ID})")
    parser.add_argument(
        "--safe-path",
        type=Path,
        help="Existing SAFE archive (.zip) or directory to analyse instead of downloading a new product",
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        choices=sorted(INDEX_SPECS.keys()),
        help="Subset of spectral indices to compute (default: all available)",
    )
    return parser.parse_args(argv)


def main(argv: Optional[Iterable[str]] = None) -> None:
    args = _parse_arguments(argv)
    logging.basicConfig(level=args.log_level)

    selected_indices = list(dict.fromkeys(args.indices or list(INDEX_SPECS.keys())))
    session: Optional[requests.Session] = None

    try:
        if args.safe_path:
            product_path = args.safe_path.expanduser().resolve()
            if not product_path.exists():
                _LOGGER.error("Provided SAFE path does not exist: %s", product_path)
                return
            product_title = _infer_product_name(product_path)
            _LOGGER.info("Using existing SAFE product at %s", product_path)
        else:
            missing_args = [name for name, value in (("geojson", args.geojson), ("start-date", args.start_date), ("end-date", args.end_date)) if value is None]
            if missing_args:
                _LOGGER.error(
                    "Missing required arguments for download: %s",
                    ", ".join(missing_args),
                )
                return
            config = authenticate_from_env(
                username=args.username,
                password=args.password,
                api_url=args.api_url,
                token_url=args.token_url,
                client_id=args.client_id,
            )
            assert args.geojson is not None
            geojson_path = args.geojson.expanduser().resolve()
            area = AreaOfInterest.from_geojson(geojson_path)

            session = create_dataspace_session(config)
            product = query_latest_product(session, config, area, args.start_date, args.end_date, tuple(args.cloud))  # type: ignore[arg-type]
            if not product:
                _LOGGER.error("No Sentinel-2 product found for the provided parameters.")
                return

            product_name = product.get("Name") or product.get("Id") or "unknown_product"
            _LOGGER.info("Downloading product %s", product_name)
            product_path = download_product(session, product, args.download_dir, config.api_url)
            product_title = _infer_product_name(product_path, fallback=product_name)

        _LOGGER.info("Extracting spectral bands")
        bands = extract_bands_from_safe(product_path, args.workdir / product_title)  # type: ignore[arg-type]

        _LOGGER.info("Computing spectral indices: %s", ", ".join(selected_indices))
        outputs = analyse_scene(bands, args.workdir / product_title / "indices", indices=selected_indices)

        for name, path in outputs.items():
            _LOGGER.info("Generated %s at %s", name.upper(), path)
    finally:
        if session is not None:
            session.close()


if __name__ == "__main__":
    main()
