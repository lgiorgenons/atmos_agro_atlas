# Plano de Migração para Arquitetura Orientada a Objetos (OO)

Este documento descreve objetivos, estado atual, arquitetura proposta, plano por fases e checklist de progresso. Será atualizado ao longo do desenvolvimento, com itens “tickados” conforme concluídos.

## Objetivos
- Separar responsabilidades (download, extração, índices, renderização, orquestração, API).
- Melhorar testabilidade (unidades isoláveis, mocks de rede/FS).
- Reutilizar e estender (novos índices, novas fontes de dados, novos mapas).
- Aumentar observabilidade (logs consistentes, métricas) e centralizar configuração.
- Manter compatibilidade com CLIs e integrações legadas durante a migração.

## Estado atual (análise)
- `core/engine/facade.WorkflowService`: já orquestra Copernicus → SafeExtractor → IndexCalculator → renderizadores.
- `core/adapters/catalog_copernicus.CopernicusClient`: encapsula OAuth2, consultas OData e download SAFE.
- `core/engine/{safe_extractor,index_calculator}`: processamento estruturado; scripts wrappers apenas delegam.
- `core/engine/renderers/*`: renderizadores OO (single-index, multi-index, true color, overlay, dashboards, etc.).
- `scripts/*.py`: wrappers finos sobre o core (mantêm CLI, opções e compatibilidade com pipelines existentes).

Riscos/limites atuais:
- Falta de cache/reuso para reprojeções e rasters intermediários.
- Parâmetros repetidos em renderizadores (tiles/clip/sharpen/vmin/vmax/...).
- Ausência de pipeline declarativo (DAG) e de suíte de testes automatizados.

## Arquitetura proposta (vision)
- `core/` (pacote raiz)
  - `cfg/settings.py` — `AppConfig` (carrega env/paths; evoluir para Settings mais robusto).
  - `adapters/catalog_copernicus.py` — `CopernicusClient` (OAuth2, OData, download SAFE).
  - `engine/safe_extractor.py` — `SafeExtractor` (extração de bandas).
  - `engine/index_calculator.py` — `IndexCalculator` (Strategy por índice).
  - `engine/renderers/` — renderizadores OO (mapas, dashboards, etc.).
  - `engine/facade.py` — `WorkflowService` (orquestra o fluxo completo).
  - `domain/` — entidades e serviços puros (value objects, contratos).
  - `pipeline/` — executores/DAGs declarativas (pendente).
  - `bindings/` — ponte para kernels nativos (opcional/futuro).
  - `scripts/` — wrappers CLI finos.
  - `tests/` — suíte unitária/integrada (a construir).

## Plano de migração (fases e tarefas)
Legenda: [ ] pendente · [x] concluído · [~] em andamento

- Fase 0 — Preparação
  - [x] Documento de plano (`todo_oop.md`).
  - [x] Layout do pacote (`core/*`) definido.
  - [x] Estrutura inicial criada.
  - [~] Configuração base (`AppConfig` pronta, falta centralizar logging e sanitizar secrets).

- Fase 1 — Fonte de dados (Copernicus)
  - [x] `CopernicusClient` (wrapper OO).
  - [x] `WorkflowService` injeta `CopernicusClient`.

- Fase 2 — Extração de bandas
  - [x] `SafeExtractor` padronizado (`extract` retorna dict de bandas).
  - [x] `FSCache` / reuso de reprojeções/arquivos.

- Fase 3 — Cálculo de índices
  - [x] `IndexCalculator` (Strategy) com NDVI, NDWI, MSI, EVI, NDRE, NDMI, NDRE1-4, CI_REDEDGE, SIPI.
  - [x] Novos índices (NDVIre, MCARI2, outros de clorofila/estresse).

- Fase 4 — Renderização
  - [x] Renderizadores principais migrados (`IndexMap`, `CSVMap`, `MultiIndex`, `TrueColor`, `Overlay`, `BandGallery`, `Comparison`, `CSVDashboard`).
  - [x] Consolidar options (tiles/clip/sharpen/vmin/vmax/upsample/smooth) em tipos compartilhados para todos os renderizadores.

- Fase 5 — Exportação
  - [x] `CSVExporter` dedicado (atualmente funções nos renderizadores).

- Fase 6 — Orquestração
  - [x] `WorkflowService` OO criado.
  - [x] CLI `scripts/run_full_workflow.py` delega ao core (fallback legado mantido).
  - [x] `core.pipeline` com executor sequencial e passos básicos (`ResolveProduct`, `ExtractBands`, `ComputeIndices`, `RenderMultiIndex`).

- Fase 7 — API
  - [x] `api/server.py` integra `WorkflowService` (execução in-processo com fallback).
  - [ ] Endpoints adicionais (jobs assíncronos, logs detalhados, catálogo de produtos).

- Fase 8 — Configuração e segurança
  - [ ] Evoluir `AppConfig` para Settings com validação (ex.: Pydantic) e reforçar logging sanitizado.

- Fase 9 — Qualidade
  - [ ] Tipagem estática (mypy) nas novas camadas.
  - [ ] Testes unitários/integrados (fixtures de raster/CSV, mocks do catálogo).
  - [ ] Documentação por módulo/classe com exemplos.

- Fase 10 — Performance e DX
  - [ ] Cache persistente para SAFE/rasters/índices (chaves por produto/parâmetro).
  - [ ] Perfis de renderização (rápido vs. qualidade) e presets reutilizáveis.

## Contratos propostos (referência)
- `CopernicusClient.get_token()` / `open_session()` / `query_latest()` / `download()`.
- `SafeExtractor.extract(product_path, workdir) -> dict[str, Path]`.
- `IndexCalculator.analyse_scene(bands, out_dir, indices) -> dict[str, Path]`.
- Renderizadores OO: `render(...) -> Path`, `prepare(...) -> PreparedRaster`.
- `WorkflowService.run_date_range(...) -> WorkflowResult`.

## Riscos e mitigação
- Divergência entre scripts e core: manter wrappers chamando serviços e validar paridade de I/O.
- Regressões visuais: comparar HTMLs gerados com cenários conhecidos (mesmas opções).
- Adoção parcial: registrar decisões no `RELATORIO_MIGRACAO_CORE.md` para garantir continuidade.

## Critérios de pronto (por fase)
- Mesmas entradas produzem mesmas saídas (paridade com legado).
- Logs úteis e erros claros.
- Tipos/documentação atualizados.

## Próximos passos imediatos
1. Implementar `FSCache` (ou estratégia equivalente) para evitar reprojeções repetidas.
2. Propagar objetos de options compartilhados para todos os renderizadores, eliminando parâmetros duplicados nos scripts.
3. Formalizar novas entidades em `core.domain` (`Scene`, `IndexResult`) e registrar contratos entre etapas.
4. Elaborar suíte de testes (fixtures de raster/CSV) cobrindo pipeline e renderizadores.

---

Progresso atual:
- [x] Plano criado e atualizado.
- [x] Estrutura `core/` consolidada.
- [x] Serviços principais migrados (CopernicusClient, SafeExtractor, IndexCalculator, WorkflowService).
- [x] Scripts CLI delegam ao core.
- [x] Renderizadores OO presentes em `core.engine.renderers`.
