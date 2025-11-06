from __future__ import annotations

import logging
from typing import Optional

from core.adapters.catalog_copernicus import CopernicusClient
from core.engine.index_calculator import IndexCalculator
from core.engine.renderers import MultiIndexMapOptions, MultiIndexMapRenderer
from core.engine.safe_extractor import SafeExtractor
from core.pipeline.base import PipelineStep
from core.pipeline.models import WorkflowContext

_LOGGER = logging.getLogger(__name__)


class ResolveProductStep(PipelineStep):
    """Resolve (ou reaproveita) o produto Sentinel-2 que será processado."""

    def __init__(self, client: Optional[CopernicusClient]):
        super().__init__("resolve_product")
        self.client = client

    def run(self, context: WorkflowContext) -> None:
        params = context.params

        if params.safe_path is not None:
            path = params.safe_path.expanduser().resolve()
            if not path.exists():
                raise RuntimeError(f"SAFE não encontrado: {path}")
            context.product_path = path
            context.product_title = CopernicusClient.infer_product_name(path)  # type: ignore[arg-type]
            _LOGGER.info("Utilizando SAFE existente: %s", context.product_title)
            return

        if self.client is None:
            raise RuntimeError("Credenciais Copernicus ausentes e nenhum SAFE local fornecido.")

        download_dir = context.config.DATA_RAW_DIR
        download_dir.mkdir(parents=True, exist_ok=True)

        with self.client.open_session() as session:
            product = self.client.query_latest(
                session=session,
                aoi=context.aoi,
                start=params.start,
                end=params.end,
                cloud=params.cloud,
            )
            if not product:
                raise RuntimeError("Nenhum produto Sentinel-2 encontrado para os parâmetros informados.")

            product_path = self.client.download(session, product, download_dir)
        context.product_path = product_path
        context.product_title = CopernicusClient.infer_product_name(product_path)
        _LOGGER.info("Produto selecionado: %s", context.product_title)


class ExtractBandsStep(PipelineStep):
    """Extrai as bandas relevantes do produto SAFE."""

    def __init__(self, extractor: SafeExtractor):
        super().__init__("extract_bands")
        self.extractor = extractor

    def run(self, context: WorkflowContext) -> None:
        if context.product_path is None or context.product_title is None:
            raise RuntimeError("Produto ainda não foi resolvido.")

        destination = context.config.DATA_PROCESSED_DIR / context.product_title
        bands = self.extractor.extract(context.product_path, destination)
        context.bands = bands
        _LOGGER.info("Bandas extraídas: %s", ", ".join(sorted(bands.keys())))


class ComputeIndicesStep(PipelineStep):
    """Calcula os índices espectrais requisitados."""

    def __init__(self, calculator: IndexCalculator):
        super().__init__("compute_indices")
        self.calculator = calculator

    def run(self, context: WorkflowContext) -> None:
        if not context.bands:
            raise RuntimeError("Nenhuma banda disponível para cálculo dos índices.")
        if context.product_title is None:
            raise RuntimeError("Produto ainda não foi resolvido.")

        indices_dir = context.config.DATA_PROCESSED_DIR / context.product_title / "indices"
        requested = list(context.params.indices) if context.params.indices is not None else None
        outputs = self.calculator.analyse_scene(context.bands, indices_dir, indices=requested)
        context.indices = outputs
        _LOGGER.info("Índices gerados: %s", ", ".join(sorted(outputs.keys())))


class RenderMultiIndexStep(PipelineStep):
    """Gera o mapa de comparação multi-índices."""

    def __init__(self, renderer: MultiIndexMapRenderer):
        super().__init__("render_multi_index_map")
        self.renderer = renderer

    def run(self, context: WorkflowContext) -> None:
        if not context.indices:
            raise RuntimeError("Nenhum índice disponível para renderização.")

        output_dir = context.config.MAPAS_DIR
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / "compare_indices_all.html"
        overlays = [context.params.aoi_path]
        index_paths = [path for _, path in sorted(context.indices.items())]

        self.renderer.render(index_paths=index_paths, output_path=output_path, overlays=overlays)
        context.register_map(output_path)
        _LOGGER.info("Mapa multi-índices gerado em %s", output_path)


def create_renderer_from_context(context: WorkflowContext) -> MultiIndexMapRenderer:
    params = context.params
    options = MultiIndexMapOptions(
        tiles=params.tiles,
        tile_attr=params.tile_attr,
        padding_factor=params.padding,
        clip=params.clip,
        upsample=params.upsample,
        smooth_radius=params.smooth_radius,
        sharpen=params.sharpen,
        sharpen_radius=params.sharpen_radius,
        sharpen_amount=params.sharpen_amount,
    )
    return MultiIndexMapRenderer(options)
