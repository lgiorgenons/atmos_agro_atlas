from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class BaseMapOptions:
    """Opções compartilhadas entre renderizadores baseados em mapas Folium."""

    tiles: str = "CartoDB positron"
    tile_attr: Optional[str] = None
    padding_factor: float = 0.3
    clip: bool = False
    upsample: float = 1.0
    smooth_radius: float = 0.0
    sharpen: bool = False
    sharpen_radius: float = 1.0
    sharpen_amount: float = 1.3
    zoom_start: int = 11
    min_zoom: int = 1
    max_zoom: int = 28
    max_native_zoom: int = 19
    allow_basemap_stretch: bool = False
