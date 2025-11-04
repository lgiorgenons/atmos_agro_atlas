# Plano de Migração para Arquitetura Orientada a Objetos (OO)

Este documento descreve objetivos, análise do estado atual, arquitetura proposta, plano de migração por fases e checklist de progresso. Será atualizado ao longo do desenvolvimento, com itens “tickados” conforme concluídos.

## Objetivos
- Separação de responsabilidades (download, extração, índices, renderização, orquestração, API).
- Testabilidade (unidades isoláveis, mocks de rede/FS).
- Reuso e extensibilidade (novos índices, novas fontes de dados, novos mapas).
- Observabilidade (logs consistentes, métricas), e configuração centralizada.
- Compatibilidade: manter CLIs existentes enquanto migramos.

## Estado atual (análise)
- `scripts/satellite_pipeline.py`: monolítico; funções puras + dataclasses (`DownloadConfig`, `AreaOfInterest`, `IndexSpec`). Faz: autenticação, consulta OData, download, extração e cálculo de índices.
- Renderização: `scripts/render_*` contém lógica sólida de mapas em funções, com dataclasses utilitárias (`PreparedRaster`).
- API: `api/server.py` agrega orquestração de jobs (dataclass `JobInfo`, payload Pydantic) e expõe endpoints e estáticos. Faz chamadas diretas aos scripts.
- Frontend: Vite/React, já com proxy para `/api`, `/mapas`, `/tabelas` (sem dependência direta da estrutura interna Python).

Riscos/limites atuais:
- Acoplamento entre etapas do pipeline em um único módulo.
- Duplicação de parâmetros (tiles, clip, sharpen, etc.) entre scripts.
- Dificuldade de mockar Copernicus/FS sem uma camada de serviço/abstração.

## Arquitetura proposta (pacotes e classes)
Estrutura sugerida (nomes podem ser ajustados):

- `core/` (pacote raiz do processamento)
  - `cfg/settings.py` — `AppConfig` (Settings simples por enquanto; evoluir para Pydantic).
  - `adapters/catalog_copernicus.py` — `CopernicusClient`: autenticação OAuth2, query OData, download SAFE.
  - `engine/safe_extractor.py` — `SafeExtractor`: extrai bandas, reprojeção/normalização.
  - `engine/index_calculator.py` — `IndexCalculator` Strategy por índice (NDVI/EVI/NDRE/...).
  - `engine/renderers/` — renderizadores OO (index, multi-index, CSV, true color, overlay, gallery, dashboards, comparison).
  - `engine/facade.py` — `WorkflowService`: orquestra download→extração→índices→mapas (faz ponte com legado).
  - `domain/` — espaço reservado para entidades/serviços puros (futuros value objects).
  - `pipeline/` — executor de DAG e definições declarativas (pendente).
  - `bindings/` — interface para kernels C++/pybind11 (pendente).
  - `scripts/` — wrappers CLI finos para manter compatibilidade.
  - `tests/` — suíte unitária/integrada (precisa ser preenchida).

Compatibilidade:
- CLIs atuais (`scripts/*.py`) permanecem como “wrappers” chamando os serviços OO gradualmente.

## Plano de migração (fases e tarefas)

Legenda: [ ] pendente · [x] concluído · [~] em andamento

- Fase 0 — Preparação
  - [x] Criar este documento de plano (`todo_oop.md`).
  - [x] Definir nome do pacote (`core`) e layout final de pastas.
  - [x] Estrutura inicial de pacotes criada (`core/` com submódulos).
  - [ ] Configuração base `AppConfig` (env vars, defaults) e logging consistente.

- Fase 1 — Fonte de dados (Copernicus)
  - [x] Extrair `CopernicusClient` (wrapper sobre funções legadas).
  - [x] Injetar `CopernicusClient` em `WorkflowService` inicial.

- Fase 2 — Extração de bandas
  - [x] `SafeExtractor`: padronizar leitura e reprojecao; API clara: `extract_bands(product_path) -> Dict[str, Path]`.
  - [ ] `FSCache`: reaproveitar reprojeções/arquivos.

- Fase 3 — Cálculo de índices
  - [x] `IndexCalculator`: interface por indice (Strategy); portar logica atual (NDVI, NDWI, MSI, EVI, NDRE, NDMI, NDRE1-4, CI_REDEDGE, SIPI).
  - [ ] Extensões planejadas: SIPI, NDVIre, MCARI2 (já citadas nas pendências).

- Fase 4 — Renderização
  - [~] `IndexMapRenderer`, `CSVMapRenderer`, `MultiIndexMapRenderer`, `TrueColorRenderer`, `OverlayRenderer`, `BandGalleryRenderer`, `ComparisonMapRenderer`, `CSVDashboardRenderer`: principais visualizacoes migradas; restam apenas casos especificos do frontend (se houver).
  - [~] Unificar parâmetros comuns (tiles, clip, sharpen, vmin/vmax, upsample, smooth) em tipos/regras centrais — `IndexMapOptions`/`MultiIndexMapOptions` criados; falta aplicar aos demais mapas.

- Fase 5 — Exportação
  - [ ] `CSVExporter`: exportação padronizada a partir de `PreparedRaster`/grades.

- Fase 6 — Orquestração
  - [x] `WorkflowService` inicial criado (usa utilitários legados).
  - [x] Adaptação do CLI `scripts/run_full_workflow.py` para usar `WorkflowService` (com fallback legado).

- Fase 7 — API
  - [x] Integrar `WorkflowService` ao `api/server.py` com execução in-processo (fallback para script).
  - [ ] Endpoints para workflow assíncrono, logs, produtos e artefatos (mantendo compatibilidade de URLs).

- Fase 8 — Configuração e segurança
  - [ ] `AppConfig` com Pydantic Settings (SENTINEL_* e paths), validação e secrets.
  - [ ] Sanitização de logs (nunca logar senhas/tokens).

- Fase 9 — Qualidade
  - [ ] Tipagem estática (mypy) nas novas camadas.
  - [ ] Testes unitários focados (CopernicusClient mocked, IndexCalculator determinístico).
  - [ ] Documentação e exemplos por classe.

- Fase 10 — Performance e DX
  - [ ] Cache de produtos SAFE e rasters/índices (chaves por produto/parâmetros).
  - [ ] Perfis de renderização (rápido vs qualidade).

## Contratos propostos (rascunho)

- `CopernicusClient`:
  - `get_token() -> str`
  - `query_latest(aoi: AreaOfInterest, start: date, end: date, cloud: tuple[int,int]) -> dict | None`
  - `download(product: dict, dst_dir: Path) -> Path`  (zip/.SAFE)

- `SafeExtractor`:
  - `extract(product_path: Path, workdir: Path) -> dict[str, Path]`  (keys: blue, green, red, rededge1..4, nir, swir1, swir2)

- `IndexCalculator`:
  - `compute(bands: dict[str, Path], indices: list[str], out_dir: Path) -> dict[str, Path]`

- `IndexMapRenderer`/`MultiIndexMapRenderer`/`TrueColorRenderer`/`OverlayRenderer`:
  - `render(..., out: Path) -> Path`

- `WorkflowService`:
  - `run(date|date_range, aoi, cloud, dirs, indices, render_opts) -> WorkflowResult`

## Riscos e mitigação
- Divergência entre scripts e serviços: manter wrappers chamando serviços e testes de paridade (inputs/outputs).
- Regressões em mapas: validar HTMLs gerados nas mesmas condições (tiles none, clip, vmin/vmax automáticos).
- Tempo de migração: fatiar por fases; publicar ganhos incrementais.

## Critérios de pronto (por fase)
- Paridade funcional (mesmas entradas → mesmos arquivos de saída).
- Logs úteis e erros claros.
- Tipos/documentação atualizados.

## Próximos passos imediatos
1) Substituir dependências residuais do procedural (`scripts.satellite_pipeline`) dentro de `core.engine.facade` por serviços próprios.
2) Estruturar `core.pipeline` (executor simples + definição de DAGs) e mapear necessidades de armazenamento/cache.
3) Montar estratégia de testes automatizados (mocks de raster/CSV) e revisar a API para consumir o core desacoplado.

---

Progresso atual:
- [x] Documento de plano criado.
- [x] Estrutura inicial de pacotes criada (`core/`).
- [x] Primeiro serviço migrado (CopernicusClient + WorkflowService).
- [x] Wrapper CLI apontando para serviços (scripts principais delegam ao core).
- [x] Renderização migrada — principais renderizadores agora vivem em `core.engine.renderers`.
