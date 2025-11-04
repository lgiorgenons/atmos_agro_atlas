from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Dict, Optional, Tuple

import requests

# Reuso das funções legadas dos scripts enquanto migramos a lógica.
from scripts.satellite_pipeline import (  # type: ignore
    authenticate_from_env,
    create_dataspace_session,
    query_latest_product,
    download_product,
    _infer_product_name,
)


@dataclass
class CopernicusConfig:
    username: str
    password: str
    api_url: str
    token_url: str
    client_id: str = "cdse-public"


class CopernicusClient:
    """Cliente OO para o Copernicus Data Space (OData + OAuth2).

    Esta versão inicial é um *wrapper* fino sobre as funções existentes em
    `scripts/satellite_pipeline.py`, para reduzir risco durante a migração.
    """

    def __init__(self, cfg: CopernicusConfig):
        self.cfg = cfg

    def open_session(self) -> requests.Session:
        """Abre uma sessão autenticada (token OAuth2 já aplicado)."""
        config = authenticate_from_env(
            username=self.cfg.username,
            password=self.cfg.password,
            api_url=self.cfg.api_url,
            token_url=self.cfg.token_url,
            client_id=self.cfg.client_id,
        )
        return create_dataspace_session(config)

    def query_latest(
        self,
        session: requests.Session,
        aoi: Dict,
        start: date,
        end: date,
        cloud: Tuple[int, int] = (0, 30),
    ) -> Optional[Dict]:
        """Consulta o produto Sentinel‑2 mais recente que atende aos filtros."""
        return query_latest_product(session, self.cfg, aoi, start.isoformat(), end.isoformat(), cloud)  # type: ignore[arg-type]

    def download(self, session: requests.Session, product: Dict, dst_dir: Path) -> Path:
        """Baixa o produto (SAFE .zip) e retorna o caminho do arquivo."""
        return download_product(session, product, dst_dir, self.cfg.api_url)

    @staticmethod
    def infer_product_name(path: Path) -> str:
        return _infer_product_name(path)

