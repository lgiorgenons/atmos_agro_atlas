from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

from core.cfg.settings import AppConfig
from core.adapters.catalog_copernicus import CopernicusClient, CopernicusConfig
from core.engine.renderers import MultiIndexMapOptions, MultiIndexMapRenderer

# Reuso das funções legadas enquanto migramos processamento
from scripts.satellite_pipeline import (  # type: ignore
    AreaOfInterest,
    extract_bands_from_safe,
    analyse_scene,
)


@dataclass
class WorkflowResult:
    product_title: str
    bands: Dict[str, Path]
    indices: Dict[str, Path]
    maps: List[Path]


class WorkflowService:
    """Orquestra o fluxo: baixar/extrair/calcular/renderizar.

    Esta primeira versão usa diretamente os utilitários legados e serve
    como ponte durante a migração para OO completa.
    """

    def __init__(self, cfg: Optional[AppConfig] = None):
        self.cfg = cfg or AppConfig()

    def _client(self) -> CopernicusClient:
        if not self.cfg.SENTINEL_USERNAME or not self.cfg.SENTINEL_PASSWORD:
            raise RuntimeError("Credenciais Copernicus ausentes em AppConfig.")
        return CopernicusClient(
            CopernicusConfig(
                username=self.cfg.SENTINEL_USERNAME,
                password=self.cfg.SENTINEL_PASSWORD,
                api_url=self.cfg.SENTINEL_API_URL,
                token_url=self.cfg.SENTINEL_TOKEN_URL,
                client_id=self.cfg.SENTINEL_CLIENT_ID,
            )
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
    ) -> WorkflowResult:
        # 1) Query/Download
        client = self._client()
        aoi = AreaOfInterest.from_geojson(aoi_geojson)
        with client.open_session() as session:
            product = client.query_latest(session, aoi.geometry, start, end, cloud)
            if not product:
                raise RuntimeError("Nenhum produto encontrado para os parâmetros informados.")
            product_path = client.download(session, product, self.cfg.DATA_RAW_DIR)
            product_title = client.infer_product_name(product_path)

        # 2) Extract bands
        work_product_dir = self.cfg.DATA_PROCESSED_DIR / product_title
        bands = extract_bands_from_safe(product_path, work_product_dir)  # type: ignore[arg-type]

        # 3) Compute indices
        idx_dir = work_product_dir / "indices"
        indices_req = list(indices) if indices is not None else None
        outputs = analyse_scene(bands, idx_dir, indices=indices_req)

        # 4) Render multi-index map
        self.cfg.MAPAS_DIR.mkdir(parents=True, exist_ok=True)
        overlays = [aoi_geojson]
        compare_all = self.cfg.MAPAS_DIR / "compare_indices_all.html"
        renderer = MultiIndexMapRenderer(
            MultiIndexMapOptions(
                tiles=tiles,
                padding_factor=padding,
                clip=True,
                upsample=upsample,
                smooth_radius=smooth_radius,
                sharpen=sharpen,
                sharpen_radius=sharpen_radius,
                sharpen_amount=sharpen_amount,
            )
        )
        renderer.render(
            index_paths=[p for _, p in sorted(outputs.items())],
            output_path=compare_all,
            overlays=overlays,
        )

        return WorkflowResult(
            product_title=product_title,
            bands=bands,
            indices=outputs,
            maps=[compare_all],
        )
