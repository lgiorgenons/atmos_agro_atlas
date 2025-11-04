from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, Optional, Tuple

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject


def _compute_index(numerator: np.ndarray, denominator: np.ndarray) -> np.ndarray:
    mask = denominator == 0
    denominator = np.where(mask, np.nan, denominator)
    index = numerator / denominator
    return np.where(np.isnan(index), 0, index)


def compute_ndvi(nir: np.ndarray, red: np.ndarray) -> np.ndarray:
    return _compute_index(nir - red, nir + red)


def compute_ndwi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    return _compute_index(nir - swir, nir + swir)


def compute_msi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    return _compute_index(swir, nir)


def compute_evi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
    denominator = nir + 6 * red - 7.5 * blue + 1
    return 2.5 * _compute_index(nir - red, denominator)


def compute_ndre(nir: np.ndarray, rededge: np.ndarray) -> np.ndarray:
    return _compute_index(nir - rededge, nir + rededge)


def compute_ndmi(nir: np.ndarray, swir: np.ndarray) -> np.ndarray:
    return _compute_index(nir - swir, nir + swir)


def compute_ndre_generic(nir: np.ndarray, rededge: np.ndarray) -> np.ndarray:
    return _compute_index(nir - rededge, nir + rededge)


def compute_ci_rededge(nir: np.ndarray, rededge4: np.ndarray) -> np.ndarray:
    return (nir / rededge4) - 1


def compute_sipi(nir: np.ndarray, red: np.ndarray, blue: np.ndarray) -> np.ndarray:
    return _compute_index(nir - blue, nir - red)


def load_raster(path: Path, reference_path: Optional[Path] = None) -> Tuple[np.ndarray, rasterio.Affine, rasterio.crs.CRS]:
    with rasterio.open(path) as src:
        data = src.read(1).astype(np.float32)
        transform = src.transform
        crs = src.crs
        height = src.height
        width = src.width

    if reference_path is not None:
        with rasterio.open(reference_path) as ref:
            if (transform != ref.transform) or (height != ref.height) or (width != ref.width):
                destination = np.empty((ref.height, ref.width), dtype=np.float32)
                reproject(
                    source=data,
                    destination=destination,
                    src_transform=transform,
                    src_crs=crs,
                    dst_transform=ref.transform,
                    dst_crs=ref.crs,
                    resampling=Resampling.bilinear,
                )
                data = destination
                transform = ref.transform
                crs = ref.crs

    return data, transform, crs


def save_raster(array: np.ndarray, template_path: Path, destination: Path) -> Path:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(template_path) as src:
        meta = src.meta.copy()
    meta.update(dtype=rasterio.float32, count=1)
    with rasterio.open(destination, "w", **meta) as dst:
        dst.write(array.astype(rasterio.float32), 1)
    return destination


@dataclass(frozen=True)
class IndexSpec:
    bands: Tuple[str, ...]
    func: Callable[..., np.ndarray]


INDEX_SPECS: Dict[str, IndexSpec] = {
    "ndvi": IndexSpec(bands=("nir", "red"), func=compute_ndvi),
    "ndwi": IndexSpec(bands=("nir", "swir1"), func=compute_ndwi),
    "msi": IndexSpec(bands=("nir", "swir1"), func=compute_msi),
    "evi": IndexSpec(bands=("nir", "red", "blue"), func=compute_evi),
    "ndre": IndexSpec(bands=("nir", "rededge4"), func=compute_ndre),
    "ndmi": IndexSpec(bands=("nir", "swir1"), func=compute_ndmi),
    "ndre1": IndexSpec(bands=("nir", "rededge1"), func=compute_ndre_generic),
    "ndre2": IndexSpec(bands=("nir", "rededge2"), func=compute_ndre_generic),
    "ndre3": IndexSpec(bands=("nir", "rededge3"), func=compute_ndre_generic),
    "ndre4": IndexSpec(bands=("nir", "rededge4"), func=compute_ndre_generic),
    "ci_rededge": IndexSpec(bands=("nir", "rededge4"), func=compute_ci_rededge),
    "sipi": IndexSpec(bands=("nir", "red", "blue"), func=compute_sipi),
}


class IndexCalculator:
    """Compute spectral indices for a scene using configurable specs."""

    def __init__(self, specs: Optional[Dict[str, IndexSpec]] = None):
        self.specs = specs or INDEX_SPECS

    def analyse_scene(
        self,
        band_paths: Dict[str, Path],
        output_dir: Path,
        indices: Optional[Iterable[str]] = None,
    ) -> Dict[str, Path]:
        requested = list(dict.fromkeys(indices)) if indices is not None else list(self.specs.keys())
        if not requested:
            raise ValueError("No spectral indices requested.")

        unknown = sorted(set(requested) - self.specs.keys())
        if unknown:
            raise ValueError(f"Unsupported indices requested: {', '.join(unknown)}")

        required = set()
        for name in requested:
            required.update(self.specs[name].bands)

        missing_bands = required - band_paths.keys()
        if missing_bands:
            raise RuntimeError(f"Missing bands for analysis: {', '.join(sorted(missing_bands))}")

        nir_data, transform, crs = load_raster(band_paths["nir"])
        band_arrays: Dict[str, np.ndarray] = {"nir": nir_data}

        for band in required - {"nir"}:
            data, _, _ = load_raster(band_paths[band], reference_path=band_paths["nir"])
            band_arrays[band] = data

        outputs: Dict[str, Path] = {}
        for name in requested:
            spec = self.specs[name]
            arrays = [band_arrays[band] for band in spec.bands]
            result = spec.func(*arrays)
            outputs[name] = save_raster(result, band_paths["nir"], output_dir / f"{name}.tif")
        return outputs
