from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from core.adapters.catalog_copernicus import CopernicusClient, CopernicusConfig
from core.cfg.settings import AppConfig
from core.engine.index_calculator import INDEX_SPECS, IndexCalculator
from core.engine.safe_extractor import DEFAULT_SENTINEL_BANDS, SafeExtractor
from core.pipeline.base import Pipeline, PipelineStep
from core.pipeline.models import WorkflowContext, WorkflowParameters
from core.pipeline.steps import (
    ComputeIndicesStep,
    ExtractBandsStep,
    RenderMultiIndexStep,
    ResolveProductStep,
    create_renderer_from_context,
)


@dataclass
class PipelineResult:
    context: WorkflowContext


class WorkflowPipeline:
    """Constrói e executa o pipeline padrão do projeto."""

    def __init__(
        self,
        cfg: Optional[AppConfig] = None,
        *,
        extractor: Optional[SafeExtractor] = None,
        calculator: Optional[IndexCalculator] = None,
    ) -> None:
        self.config = cfg or AppConfig()
        self.extractor = extractor or SafeExtractor(DEFAULT_SENTINEL_BANDS.copy())
        self.calculator = calculator or IndexCalculator(INDEX_SPECS)

    def run(self, params: WorkflowParameters) -> PipelineResult:
        context = WorkflowContext(config=self.config, params=params)
        steps = self._build_steps(context)
        pipeline = Pipeline(steps)
        pipeline.run(context)
        return PipelineResult(context=context)

    def _build_steps(self, context: WorkflowContext) -> Iterable[PipelineStep]:
        params = context.params
        client = self._build_client_if_needed(params)
        renderer = create_renderer_from_context(context)

        return [
            ResolveProductStep(client),
            ExtractBandsStep(self.extractor),
            ComputeIndicesStep(self.calculator),
            RenderMultiIndexStep(renderer),
        ]

    def _build_client_if_needed(self, params: WorkflowParameters) -> Optional[CopernicusClient]:
        if params.safe_path is not None:
            return None

        username = self.config.SENTINEL_USERNAME
        password = self.config.SENTINEL_PASSWORD
        if not username or not password:
            raise RuntimeError(
                "Credenciais Copernicus ausentes. Configure SENTINEL_USERNAME/SENTINEL_PASSWORD "
                "ou informe um SAFE local pelo parâmetro safe_path."
            )

        return CopernicusClient(
            CopernicusConfig(
                username=username,
                password=password,
                api_url=self.config.SENTINEL_API_URL,
                token_url=self.config.SENTINEL_TOKEN_URL,
                client_id=self.config.SENTINEL_CLIENT_ID,
            )
        )

