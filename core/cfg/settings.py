from __future__ import annotations

from pathlib import Path
from typing import Optional
import os


class AppConfig:
    """Configurações centrais com leitura simples de variáveis de ambiente.

    Mantém compatibilidade com os nomes SENTINEL_* e diretórios padrão.
    Permite override explícito via kwargs no construtor.
    """

    def __init__(
        self,
        *,
        SENTINEL_USERNAME: Optional[str] = None,
        SENTINEL_PASSWORD: Optional[str] = None,
        SENTINEL_API_URL: Optional[str] = None,
        SENTINEL_TOKEN_URL: Optional[str] = None,
        SENTINEL_CLIENT_ID: Optional[str] = None,
        DATA_RAW_DIR: Optional[Path] = None,
        DATA_PROCESSED_DIR: Optional[Path] = None,
        MAPAS_DIR: Optional[Path] = None,
        TABELAS_DIR: Optional[Path] = None,
        DADOS_DIR: Optional[Path] = None,
    ) -> None:
        # Credenciais
        self.SENTINEL_USERNAME = SENTINEL_USERNAME or os.environ.get("SENTINEL_USERNAME")
        self.SENTINEL_PASSWORD = SENTINEL_PASSWORD or os.environ.get("SENTINEL_PASSWORD")
        self.SENTINEL_API_URL = (
            SENTINEL_API_URL
            or os.environ.get("SENTINEL_API_URL")
            or "https://catalogue.dataspace.copernicus.eu/odata/v1/"
        )
        self.SENTINEL_TOKEN_URL = (
            SENTINEL_TOKEN_URL
            or os.environ.get("SENTINEL_TOKEN_URL")
            or "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token"
        )
        self.SENTINEL_CLIENT_ID = (
            SENTINEL_CLIENT_ID or os.environ.get("SENTINEL_CLIENT_ID") or "cdse-public"
        )

        # Diretórios
        self.DATA_RAW_DIR = DATA_RAW_DIR or Path(os.environ.get("DATA_RAW_DIR") or "data/raw")
        self.DATA_PROCESSED_DIR = DATA_PROCESSED_DIR or Path(
            os.environ.get("DATA_PROCESSED_DIR") or "data/processed"
        )
        self.MAPAS_DIR = MAPAS_DIR or Path(os.environ.get("MAPAS_DIR") or "mapas")
        self.TABELAS_DIR = TABELAS_DIR or Path(os.environ.get("TABELAS_DIR") or "tabelas")
        self.DADOS_DIR = DADOS_DIR or Path(os.environ.get("DADOS_DIR") or "dados")

