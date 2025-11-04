# Domain Layer

Entidades, Value Objects e contratos (Ports) que descrevem o domínio de processamento Sentinel-2.
Nenhuma dependência externa deve ser utilizada aqui. Exemplos esperados:

- `entities.py`: ProductScene, BandSet, AOI, IndexOutput, Alert.
- `services.py`: validações de parâmetros, transformações matemáticas puras.
- `ports.py`: CatalogPort, StoragePort, RasterPort, AlertPort, RepoPort.

Futuros módulos usarão essa camada para orquestrar o processamento sem acoplamento a bibliotecas específicas.
