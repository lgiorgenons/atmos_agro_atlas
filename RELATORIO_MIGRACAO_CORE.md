## Progresso da migração para o core (sessão atual)

- Migrei os renderizadores principais para `core/engine/renderers/`:
  - `IndexMapRenderer` agora lida com mapas single-index e exportacao CSV, substituindo a logica procedural antiga.
  - `CSVMapRenderer` reconstrói grades a partir dos CSVs exportados.
  - `TrueColorRenderer` gera a composicao RGB em classe reutilizavel.
  - `TrueColorOverlayRenderer` combina true color com camadas de indices (CSV) alternaveis.
  - `BandGalleryRenderer` gera a galeria de bandas Sentinel-2, `ComparisonMapRenderer` oferece o mapa DualMap e `CSVDashboardRenderer` compõe o dashboard tabulado.
- Criei utilidades compartilhadas (`csv_utils.py`, `geoutils.py`, `raster.py`) eliminando duplicação de código entre scripts.
- Atualizei os scripts CLI (`render_index_map.py`, `render_csv_map.py`, `render_truecolor_map.py`, `render_truecolor_overlay_map.py`, `export_indices_csv.py`) para atuarem como wrappers finos que instanciam as classes do core.
- Ajustei `scripts/run_full_workflow.py` e `api/server.py` para priorizarem os renderizadores orientados a objetos, mantendo fallback para versoes legadas.
- Sincronizei documentacao em `README.md`, `CONTEXTO.md` e `todo_oop.md` com o novo estado da arquitetura.
- Iniciei a camada de processamento com `SafeExtractor` em `core.engine.safe_extractor`, mantendo `extract_bands_from_safe` como wrapper.

## Itens ainda pendentes após a sessão

1. Portar renderizadores restantes (ex.: comparativos específicos do frontend) caso necessário.
2. Continuar a camada de processamento implementando `IndexCalculator` e demais estratégias de índices dentro de `core.engine`.
3. Revisar o fluxo da API apos a migracao completa (novos endpoints e governanca dos jobs).
4. Planejar testes automatizados (mocks de CSV/raster) para as novas classes antes de seguir com o restante da refatoracao.
