# Core Package Layout (`core`)

```
core/
  domain/        # entidades e serviços puros (Clean/Hexagonal)
  engine/        # fachada, estratégias, renderers e passos do workflow
  adapters/      # implementações concretas (catálogo, storage, alertas)
  pipeline/      # executores de DAG e definições declarativas (YAML)
  cfg/           # configuração central (AppConfig, loaders)
  bindings/      # ponte para kernels C++/pybind11 quando disponível
  scripts/       # wrappers CLI finos para retrocompatibilidade
  tests/         # testes unitários e de integração do core
```

O objetivo é consolidar todo o processamento pesado e renderização aqui, deixando
a futura API/web apenas como consumidor dos serviços expostos pelo core.

Durante a migração mantemos *wrappers* em `scripts/` que chamam as novas classes;
isso permite atualizar notebooks, CLI e automações sem quebrar fluxos existentes.

## Architecture Pattern
- Hexagonal/Clean Architecture: domínio e motor de processamento ficam isolados no pacote `core`, enquanto scripts/API atuam como adaptadores externos.
- Ports & Adapters: `core/engine` expõe serviços e renderizadores; `core/adapters` implementa integrações como `CopernicusClient`.
- Service Objects + Options: cada renderer (`ComparisonMapRenderer`, `IndexMapRenderer`, etc.) encapsula a lógica em classes com objetos de configuração (`*Options`) para facilitar reuso e testagem.
