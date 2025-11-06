from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable, Tuple

import numpy as np
from affine import Affine
from rasterio.transform import xy


class CSVExporter:
    """Exporta valores rasterizados para CSV (lon, lat, value)."""

    def __init__(self, *, fieldnames: Tuple[str, str, str] = ("longitude", "latitude", "value")) -> None:
        self.fieldnames = fieldnames

    def export(self, data: np.ndarray, transform: Affine, output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", newline="", encoding="utf-8") as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(self.fieldnames)
            for row_idx, row in enumerate(data):
                valid = np.isfinite(row)
                if not np.any(valid):
                    continue
                cols = np.nonzero(valid)[0]
                lons, lats = self._coordinates(transform, row_idx, cols)
                for lon, lat, col_idx in zip(lons, lats, cols):
                    writer.writerow([lon, lat, float(row[col_idx])])
        return output_path

    @staticmethod
    def _coordinates(transform: Affine, row: int, columns: Iterable[int]) -> Tuple[np.ndarray, np.ndarray]:
        rows_iter = [row] * len(columns)
        lons, lats = xy(transform, rows_iter, list(columns), offset="center")
        return np.asarray(lons), np.asarray(lats)
