# Pipeline

Executores e definições de DAG responsáveis por encadear os passos do workflow.

- `dag_executor.py`: resolver ordem/topologia, retries, logging.
- `dags/*.yaml`: representações declarativas (ex.: full_workflow, incremental).

A camada de aplicação (CLI/API) irá carregar os DAGs e executar via engine facade.
