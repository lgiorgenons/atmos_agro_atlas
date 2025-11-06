from __future__ import annotations

from pathlib import Path
from typing import Optional, Sequence, Tuple

import numpy as np
import rasterio
from matplotlib import colormaps, colors
from rasterio.enums import Resampling
from rasterio.transform import array_bounds
from rasterio.warp import calculate_default_transform, reproject, transform_bounds
from scipy.ndimage import gaussian_filter

TARGET_CRS = "EPSG:4326"


def load_raster(
    path: Path,
    clip_bounds_wgs84: Optional[Tuple[float, float, float, float]] = None,
) -> Tuple[np.ndarray, rasterio.Affine, Sequence[float]]:
    """Read a GeoTIFF band and reproject to WGS84."""
    with rasterio.open(path) as src:
        if clip_bounds_wgs84 is not None:
            left, bottom, right, top = transform_bounds(TARGET_CRS, src.crs, *clip_bounds_wgs84, densify_pts=21)
            left = max(left, src.bounds.left)
            bottom = max(bottom, src.bounds.bottom)
            right = min(right, src.bounds.right)
            top = min(top, src.bounds.top)
            if left >= right or bottom >= top:
                raise ValueError(
                    "O GeoJSON informado não intersecta o raster solicitado. "
                    "Revise a área de interesse ou utilize --no-clip."
                )
            window = rasterio.windows.from_bounds(left, bottom, right, top, transform=src.transform).round_offsets().round_lengths()
            data = src.read(1, window=window).astype(np.float32)
            src_transform = src.window_transform(window)
            src_bounds = (left, bottom, right, top)
        else:
            data = src.read(1).astype(np.float32)
            src_transform = src.transform
            src_bounds = src.bounds

        nodata = src.nodata
        if nodata is not None:
            data = np.where(data == nodata, np.nan, data)
        elif np.ma.isMaskedArray(data):
            data = data.filled(np.nan)

        dst_transform, width, height = calculate_default_transform(
            src.crs, TARGET_CRS, data.shape[1], data.shape[0], *src_bounds
        )

        destination = np.full((height, width), np.nan, dtype=np.float32)
        reproject(
            source=data,
            destination=destination,
            src_transform=src_transform,
            src_crs=src.crs,
            dst_transform=dst_transform,
            dst_crs=TARGET_CRS,
            src_nodata=nodata if nodata is not None else None,
            dst_nodata=np.nan,
            resampling=Resampling.bilinear,
        )

    bounds = array_bounds(destination.shape[0], destination.shape[1], dst_transform)
    return destination, dst_transform, bounds


def apply_unsharp_mask(array: np.ndarray, radius: float, amount: float) -> np.ndarray:
    """Enhance contrast using an unsharp mask while respecting NaNs."""
    mask = np.isfinite(array)
    if not np.any(mask):
        return array
    valid = array[mask]
    fill_value = float(np.nanmean(valid)) if valid.size else 0.0
    filled = np.where(mask, array, fill_value)
    blurred = gaussian_filter(filled, sigma=radius, mode="nearest")
    sharpened = filled + amount * (filled - blurred)
    return np.where(mask, sharpened, np.nan)


def apply_smoothing(array: np.ndarray, sigma: float) -> np.ndarray:
    """Apply gaussian smoothing if sigma > 0."""
    if sigma and sigma > 0:
        return gaussian_filter(array, sigma=float(sigma))
    return array


def upsample_raster(
    data: np.ndarray,
    transform: rasterio.Affine,
    factor: float,
) -> Tuple[np.ndarray, rasterio.Affine]:
    """Upsample the raster by the given factor preserving georeferencing."""
    if factor is None or factor <= 1:
        return data, transform
    h, w = data.shape
    new_h, new_w = int(h * factor), int(w * factor)
    destination = np.empty((new_h, new_w), dtype=np.float32)
    new_transform = rasterio.Affine(transform.a / factor, transform.b, transform.c, transform.d, transform.e / factor, transform.f)
    reproject(
        source=data,
        destination=destination,
        src_transform=transform,
        src_crs=TARGET_CRS,
        dst_transform=new_transform,
        dst_crs=TARGET_CRS,
        src_nodata=np.nan,
        dst_nodata=np.nan,
        resampling=Resampling.bilinear,
    )
    return destination, new_transform


def generate_rgba(
    data: np.ndarray,
    cmap_name: str,
    vmin: Optional[float],
    vmax: Optional[float],
    opacity: float,
) -> Tuple[np.ndarray, float, float]:
    """Convert a raster into an RGBA image with alpha based on validity."""
    valid = np.isfinite(data)
    if not np.any(valid):
        raise RuntimeError("Raster nao possui pixels validos para renderizacao.")
    finite_values = data[valid]
    min_value = vmin if vmin is not None else float(np.nanpercentile(finite_values, 2))
    max_value = vmax if vmax is not None else float(np.nanpercentile(finite_values, 98))
    if np.isclose(min_value, max_value):
        max_value = min_value + 1e-3
    cmap = colormaps[cmap_name]
    normaliser = colors.Normalize(vmin=min_value, vmax=max_value, clip=True)
    rgba = cmap(normaliser(data))
    rgba[..., 3] = np.where(valid, opacity, 0.0)
    image = (rgba * 255).astype(np.uint8)
    return image, min_value, max_value
