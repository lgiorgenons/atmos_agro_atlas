# Adapters

Implementações concretas dos ports definidos em `core/domain/ports.py`.

Exemplos planejados:
- `catalog_copernicus.py`: consulta ao Catálogo OData (Copernicus Data Space).
- `raster_rasterio.py`: leitura/escrita de rasters usando rasterio/GDAL.
- `storage_fs.py` / `storage_s3.py`: persistência local ou em S3/MinIO.
- `alerts_db.py`: integração com banco de dados para salvar alertas e insights.

Esses adapters podem ser trocados conforme ambiente (local, cloud, testes).
