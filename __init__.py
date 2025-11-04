"""canasat – Toolkit OO para monitoramento da cana via satélite.

Este pacote fornece camadas orientadas a objetos para:
- acesso a dados (Copernicus Data Space),
- extração e processamento de bandas/índices,
- renderização de mapas,
- e orquestração de workflows.

Os scripts existentes em `scripts/` continuam funcionando; as classes
de `canasat` serão chamadas por eles gradualmente durante a migração.
"""

__all__ = [
    "config",
    "datasources",
    "workflow",
]

