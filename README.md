# Cana Vision Core

Toolkit responsável por todo o processamento e geração de produtos de imagens Sentinel‑2 para o projeto Cana Vision.

## Estrutura Geral

```
core/
  domain/        # entidades e regras puras (Clean/Hexagonal)
  engine/        # fachada, renderers, cálculos de índices, steps de workflow
  adapters/      # integrações externas (Copernicus, storage, alertas, etc.)
  pipeline/      # orquestração declarativa (executores e DAGs)
  cfg/           # configuração central (AppConfig, carregamento de env)
  bindings/      # ponte para kernels C++/pybind11 (opcional)
  scripts/       # CLI wrappers finos para retrocompatibilidade
  tests/         # testes unitários e de integração
scripts/
  *.py           # wrappers chamando as classes do core
```

## Arquitetura

- **Hexagonal / Clean Architecture:** o pacote `core` concentra o domínio e os serviços principais; camadas externas (scripts, futura API) consomem o core como adaptadores.
- **Ports & Adapters:** `core/engine` fornece ports (serviços/fachadas), enquanto `core/adapters` implementa integrações concretas (ex.: `CopernicusClient`).
- **Service Objects + Options:** renderizadores e processadores usam classes específicas com objetos de configuração (`*Options`) para facilitar reuso, testes e parametrização.

## Componentes principais

- `core/engine/safe_extractor.py` — `SafeExtractor` extrai e normaliza bandas Sentinel‑2 (GeoTIFF).
- `core/engine/index_calculator.py` — `IndexCalculator` implementa índices espectrais (NDVI, NDWI, NDRE, MSI, etc.).
- `core/engine/renderers/` — renderers orientados a objetos (mapa single index, multiindex, CSV, true color, overlay, dashboards, compara).
- `core/engine/facade.py` — `WorkflowService` reúne download → extração → índices → mapas, servindo como ponte de migração.
- `core/adapters/catalog_copernicus.py` — `CopernicusClient` encapsula autenticação e download via Copernicus Data Space.
- `core/cfg/settings.py` — `AppConfig` centraliza diretórios padrão e credenciais lidas do ambiente.

## Como executar

```bash
python -m venv .venv
source .venv/bin/activate               # ou .\.venv\Scripts\activate no Windows
pip install -r requirements.txt

# Exemplo (CLI legacy): executar workflow completo
python scripts/run_full_workflow.py \
  --date 2025-01-10 \
  --geojson dados/map.geojson \
  --cloud 0 30

# Novo entry point direto no core
python -m core.scripts.run_workflow \
  --date-range 2025-01-01 2025-01-31 \
  --geojson dados/map.geojson \
  --cloud 0 30

# Gerar mapa de índices
python scripts/render_index_map.py --index data/processed/<produto>/indices/ndvi.tif
```

Durante a transição, os scripts em `scripts/` permanecem como wrappers finos das classes do core, garantindo compatibilidade com pipelines existentes.
