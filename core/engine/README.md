# Engine Layer

Fachada de alto nível (`facade.py`), estratégias de cálculo (`indices/`), renderização (`renderers/`) e passos do workflow (`steps/`).

Responsabilidades:
- Orquestrar o pipeline (download → extração → índices → exportação).
- Registrar estratégias de índices/visualizações via pattern Strategy.
- Implementar Template Method para etapas do workflow (download, extract, compute, export).
- Expor APIs simplificadas: `run_workflow`, `compute_indices`, `render_maps`.
