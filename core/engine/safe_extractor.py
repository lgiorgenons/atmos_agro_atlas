from __future__ import annotations

import logging
import tempfile
import zipfile
from pathlib import Path
from typing import Dict, Optional

import rasterio

DEFAULT_SENTINEL_BANDS: Dict[str, str] = {
    "B01": "coastal",
    "B02": "blue",
    "B03": "green",
    "B04": "red",
    "B05": "rededge1",
    "B06": "rededge2",
    "B07": "rededge3",
    "B08": "nir",
    "B8A": "rededge4",
    "B09": "water_vapor",
    "B10": "cirrus",
    "B11": "swir1",
    "B12": "swir2",
}

_LOGGER = logging.getLogger(__name__)


class SafeExtractor:
    """Extrai bandas Sentinel-2 de um arquivo SAFE (zip ou pasta)."""

    def __init__(self, bands: Optional[Dict[str, str]] = None) -> None:
        self.bands = bands or DEFAULT_SENTINEL_BANDS

    def extract(self, safe_archive: Path, destination: Path) -> Dict[str, Path]:
        destination.mkdir(parents=True, exist_ok=True)

        tmp_dir: Optional[tempfile.TemporaryDirectory[str]] = None
        if safe_archive.suffix == ".zip":
            tmp_dir = tempfile.TemporaryDirectory(prefix="safe_")
            tmp_path = Path(tmp_dir.name)
            _LOGGER.info("Extracting SAFE archive %s", safe_archive)
            with zipfile.ZipFile(safe_archive) as archive:
                archive.extractall(tmp_path)
            safe_root = next(tmp_path.glob("*.SAFE"))
        else:
            safe_root = safe_archive

        extracted: Dict[str, Path] = {}
        for band_id, alias in self.bands.items():
            try:
                jp2_path = self._locate_band(safe_root, band_id)
            except FileNotFoundError:
                _LOGGER.warning("Band %s not found in SAFE structure", band_id)
                continue

            tif_path = destination / f"{alias}.tif"
            if tif_path.exists():
                try:
                    tif_mtime = tif_path.stat().st_mtime
                    jp2_mtime = jp2_path.stat().st_mtime
                    if tif_mtime >= jp2_mtime:
                        _LOGGER.debug("Reusing cached band %s at %s", alias, tif_path)
                        extracted[alias] = tif_path
                        continue
                except OSError:
                    pass

            with rasterio.open(jp2_path) as src:
                profile = src.profile
                data = src.read(1)

            profile.update(driver="GTiff")
            with rasterio.open(tif_path, "w", **profile) as dst:
                dst.write(data, 1)

            extracted[alias] = tif_path

        if tmp_dir is not None:
            tmp_dir.cleanup()

        return extracted

    @staticmethod
    def _locate_band(safe_root: Path, band: str) -> Path:
        patterns = [
            f"**/IMG_DATA/*/*_{band}_*.jp2",
            f"**/IMG_DATA/*_{band}_*.jp2",
            f"**/IMG_DATA/**/*_{band}_*.jp2",
        ]
        for pattern in patterns:
            matches = list(safe_root.glob(pattern))
            if matches:
                matches.sort(key=lambda p: ("10m" not in p.name, "20m" in p.name, p.name))
                return matches[0]
        raise FileNotFoundError(f"Band {band} not found inside {safe_root}")
