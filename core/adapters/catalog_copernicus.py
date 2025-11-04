from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Dict, Optional, Tuple
from urllib.parse import urljoin

import requests

from core.domain import AreaOfInterest

_LOGGER = logging.getLogger(__name__)
_REQUEST_TIMEOUT = 60


@dataclass
class CopernicusConfig:
    username: str
    password: str
    api_url: str
    token_url: str
    client_id: str = "cdse-public"


class CopernicusClient:
    """Cliente OO para o Copernicus Data Space (OData + OAuth2).

    Encapsula autenticação, consulta via OData e download de produtos Sentinel-2.
    """

    def __init__(self, cfg: CopernicusConfig):
        self.cfg = cfg

    def open_session(self) -> requests.Session:
        """Abre uma sessão autenticada (token OAuth2 já aplicado)."""
        payload = {
            "grant_type": "password",
            "client_id": self.cfg.client_id,
            "username": self.cfg.username,
            "password": self.cfg.password,
        }
        response = requests.post(self.cfg.token_url, data=payload, timeout=_REQUEST_TIMEOUT)
        response.raise_for_status()

        token = response.json().get("access_token")
        if not token:
            raise RuntimeError("Failed to obtain access token from Copernicus Data Space.")

        session = requests.Session()
        session.headers.update({"Authorization": f"Bearer {token}"})
        return session

    def query_latest(
        self,
        session: requests.Session,
        aoi: AreaOfInterest,
        start: date,
        end: date,
        cloud: Tuple[int, int] = (0, 30),
    ) -> Optional[Dict]:
        """Consulta o produto Sentinel‑2 mais recente que atende aos filtros."""
        start_timestamp = f"{start.isoformat()}T00:00:00Z"
        end_timestamp = f"{(end + timedelta(days=1)).isoformat()}T00:00:00Z"
        footprint_wkt = aoi.to_wkt()

        min_cloud, max_cloud = cloud
        cloud_filters: list[str] = []
        if min_cloud > 0:
            cloud_filters.append(
                "Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
                f"and att/OData.CSC.DoubleAttribute/Value ge {float(min_cloud):.2f})"
            )
        cloud_filters.append(
            "Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' "
            f"and att/OData.CSC.DoubleAttribute/Value le {float(max_cloud):.2f})"
        )
        product_type_filter = (
            "Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' "
            "and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A')"
        )

        filter_parts = [
            "Collection/Name eq 'SENTINEL-2'",
            f"ContentDate/Start ge {start_timestamp}",
            f"ContentDate/Start lt {end_timestamp}",
            f"OData.CSC.Intersects(Footprint, geography'SRID=4326;{footprint_wkt}')",
            product_type_filter,
        ]
        filter_parts.extend(cloud_filters)

        params = {
            "$filter": " and ".join(filter_parts),
            "$orderby": "ContentDate/Start desc",
            "$top": "1",
        }

        products_url = urljoin(self.cfg.api_url.rstrip("/") + "/", "Products")
        response = session.get(products_url, params=params, timeout=_REQUEST_TIMEOUT)
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:  # pragma: no cover - log para diagnósticos
            _LOGGER.error("OData query failed: %s", response.text)
            raise exc

        payload = response.json()
        products = payload.get("value", [])
        if not products:
            return None
        return products[0]

    def download(self, session: requests.Session, product: Dict, dst_dir: Path) -> Path:
        """Baixa o produto (SAFE .zip) e retorna o caminho do arquivo."""
        dst_dir.mkdir(parents=True, exist_ok=True)

        product_id = product.get("Id")
        if not product_id:
            raise RuntimeError("Product payload missing 'Id' field.")

        product_name = product.get("Name") or str(product_id)
        archive_name = product_name if product_name.endswith(".zip") else f"{product_name}.zip"
        download_url = urljoin(self.cfg.api_url.rstrip("/") + "/", f"Products({product_id})/$value")

        target_path = dst_dir / archive_name
        current_url = download_url
        for _ in range(5):
            response = session.get(
                current_url,
                stream=True,
                timeout=_REQUEST_TIMEOUT * 10,
                allow_redirects=False,
            )
            if response.is_redirect:
                location = response.headers.get("Location")
                if not location:
                    break
                current_url = urljoin(current_url, location)
                continue
            break
        else:  # pragma: no cover - cenário raro
            raise RuntimeError("Exceeded maximum number of redirects while downloading product.")

        with response:
            if response.status_code >= 400:
                _LOGGER.error("Download request failed (%s): %s", response.status_code, response.text)
                response.raise_for_status()
            with target_path.open("wb") as file:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        file.write(chunk)
        return target_path

    @staticmethod
    def infer_product_name(path: Path) -> str:
        stem = path.stem
        if stem.endswith(".SAFE"):
            stem = stem[:-5]
        return stem or path.name
