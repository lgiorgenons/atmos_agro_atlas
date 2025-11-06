from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from core.cfg.settings import AppConfig
from core.engine.index_calculator import INDEX_SPECS, IndexCalculator
from core.engine.safe_extractor import DEFAULT_SENTINEL_BANDS, SafeExtractor
from core.pipeline.executor import WorkflowPipeline
from core.pipeline.models import WorkflowParameters


@dataclass
class WorkflowResult:
    product_title: str
    bands: Dict[str, Path]
    indices: Dict[str, Path]
    maps: List[Path]


class WorkflowService:
    """Orquestra o fluxo de processamento reutilizando o pipeline do core."""

    def __init__(
        self,
        cfg: Optional[AppConfig] = None,
        *,
        extractor: Optional[SafeExtractor] = None,
        calculator: Optional[IndexCalculator] = None,
    ):
        self.cfg = cfg or AppConfig()
        self.extractor = extractor or SafeExtractor(DEFAULT_SENTINEL_BANDS.copy())
        self.calculator = calculator or IndexCalculator(INDEX_SPECS)

        self.pipeline = WorkflowPipeline(
            self.cfg,
            extractor=self.extractor,
            calculator=self.calculator,
        )

    def run_date_range(
        self,
        *,
        start: date,
        end: date,
        aoi_geojson: Path,
        cloud: Tuple[int, int] = (0, 30),
        indices: Optional[Iterable[str]] = None,
        upsample: float = 12.0,
        smooth_radius: float = 1.0,
        sharpen: bool = True,
        sharpen_radius: float = 1.2,
        sharpen_amount: float = 1.5,
        tiles: str = "none",
        padding: float = 0.3,
        safe_path: Optional[Path] = None,
    ) -> WorkflowResult:
        params = WorkflowParameters(
            start=start,
            end=end,
            aoi_path=aoi_geojson,
            cloud=cloud,
            indices=list(indices) if indices is not None else None,
            upsample=upsample,
            smooth_radius=smooth_radius,
            sharpen=sharpen,
            sharpen_radius=sharpen_radius,
            sharpen_amount=sharpen_amount,
            tiles=tiles,
            padding=padding,
            safe_path=safe_path,
        )
        result = self.pipeline.run(params).context
        if result.product_title is None:
            raise RuntimeError("Título do produto não definido após execução do pipeline.")
        return WorkflowResult(
            product_title=result.product_title,
            bands=result.bands,
            indices=result.indices,
            maps=result.maps,
        )
