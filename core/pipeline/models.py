from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from core.cfg.settings import AppConfig
from core.domain import AreaOfInterest


@dataclass(frozen=True)
class WorkflowParameters:
    """Parâmetros imutáveis utilizados para executar o workflow."""

    start: date
    end: date
    aoi_path: Path
    cloud: Tuple[int, int] = (0, 30)
    indices: Optional[Iterable[str]] = None
    upsample: float = 12.0
    smooth_radius: float = 1.0
    sharpen: bool = True
    sharpen_radius: float = 1.2
    sharpen_amount: float = 1.5
    tiles: str = "none"
    tile_attr: Optional[str] = None
    padding: float = 0.3
    clip: bool = True
    safe_path: Optional[Path] = None


@dataclass
class WorkflowContext:
    """Estado compartilhado entre os passos do pipeline."""

    config: AppConfig
    params: WorkflowParameters
    product_path: Optional[Path] = None
    product_title: Optional[str] = None
    bands: Dict[str, Path] = field(default_factory=dict)
    indices: Dict[str, Path] = field(default_factory=dict)
    maps: List[Path] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.aoi = AreaOfInterest.from_geojson(self.params.aoi_path)

    def register_map(self, path: Path) -> None:
        self.maps.append(path)

