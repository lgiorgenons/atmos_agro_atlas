# Core de Processamento (`canasat`)

Este módulo concentra todo o processamento de imagens Sentinel‑2 (download, extração de bandas, cálculo de índices e renderização de produtos). Os antigos scripts permaneceram como _wrappers_ finos para manter compatibilidade, mas toda a lógica vive aqui.

## Requisitos

- Python 3.10 ou superior  
- Dependências listadas em `requirements.txt`

## Instalação e ambiente

```bash
python -m venv .venv
source .venv/bin/activate        # PowerShell: .\.venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install -r requirements.txt
```

## Scripts úteis (agora wrappers do core)

```bash
# Pipeline completo: download → índices → mapas → CSV
python scripts/run_full_workflow.py \
  --date 2025-10-20 \
  --geojson dados/map.geojson \
  --cloud 0 30 \
  --username "$SENTINEL_USERNAME" \
  --password "$SENTINEL_PASSWORD"

# Galeria de bandas Sentinel-2
python scripts/render_band_gallery.py --product-dir data/processed/<produto>

# Dashboard com true color + índices (CSV)
python scripts/render_csv_dashboard.py \
  --csv-dir tabelas \
  --truecolor-red data/processed/<produto>/red.tif \
  --truecolor-green data/processed/<produto>/green.tif \
  --truecolor-blue data/processed/<produto>/blue.tif

# Comparação dual-map (basemap × índice)
python scripts/render_comparison_map.py \
  --index data/processed/<produto>/indices/ndvi.tif \
  --geojson dados/map.geojson
```

> Todos os renderizadores (index, CSV, true color, overlay, galeria, dashboards) estão implementados como classes em `canasat.rendering.*`. Os scripts acima apenas configuram as opções e chamam `render(...)`.

## Componentes principais

- `canasat.processing`
  - `SafeExtractor`: extrai e normaliza as bandas de um SAFE.
  - `IndexCalculator`: calcula NDVI, NDWI, MSI, NDRE, NDMI, CI Red-Edge, SIPI etc.
- `canasat.rendering`
  - `IndexMapRenderer`, `CSVMapRenderer`, `CSVDashboardRenderer`
  - `TrueColorRenderer`, `TrueColorOverlayRenderer`, `MultiIndexMapRenderer`
  - `BandGalleryRenderer`, `ComparisonMapRenderer`
- `canasat.workflow`
  - `WorkflowService`: orquestra download → extração → índices → mapas.

## Documentação complementar

- `docs/core/CONTEXTO.md` – visão geral do projeto.
- `docs/core/RELATORIO_MIGRACAO_CORE.md` – histórico das migrações.
- `docs/core/todo_oop.md` – checklist detalhado das próximas fases.
- `docs/core/Analise_Detalhada_Sindrome_Murcha_Cana.md` – base agronômica usada no design do pipeline.
