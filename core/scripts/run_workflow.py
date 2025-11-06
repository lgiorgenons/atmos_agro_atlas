from __future__ import annotations
import argparse
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Optional, Sequence, Tuple

from core.engine.facade import WorkflowService


def _parse_date(value: str) -> date:
    try:
        return datetime.fromisoformat(value).date()
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Data inválida: {value}") from exc


def _resolve_dates(args: argparse.Namespace) -> Tuple[date, date]:
    if args.date:
        dt = _parse_date(args.date)
        return dt, dt
    if args.date_range:
        start = _parse_date(args.date_range[0])
        end = _parse_date(args.date_range[1])
        if end < start:
            start, end = end, start
        return start, end
    raise argparse.ArgumentError(None, "Informe --date ou --date-range.")


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Executa o workflow completo (download -> bandas -> índices -> mapas) usando o core OO."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date", help="Data única no formato YYYY-MM-DD.")
    group.add_argument("--date-range", nargs=2, metavar=("START", "END"), help="Intervalo YYYY-MM-DD YYYY-MM-DD.")

    parser.add_argument("--geojson", type=Path, default=Path("dados/map.geojson"), help="Arquivo GeoJSON da área.")
    parser.add_argument(
        "--cloud",
        type=int,
        nargs=2,
        default=(0, 30),
        metavar=("MIN", "MAX"),
        help="Faixa de cobertura de nuvens aceitável (default: 0 30).",
    )
    parser.add_argument(
        "--indices",
        nargs="+",
        help="Lista de índices a serem calculados (default: todos suportados).",
    )
    parser.add_argument("--tiles", default="none", help="Camada base utilizada no mapa multi-índices.")
    parser.add_argument("--tile-attr", default=None, help="Atribuição personalizada para a camada base.")
    parser.add_argument("--padding", type=float, default=0.3, help="Fator de expansão do envelope do GeoJSON.")
    parser.add_argument("--upsample", type=float, default=12.0, help="Fator de upsample antes da suavização.")
    parser.add_argument("--smooth-radius", type=float, default=1.0, help="Raio da suavização gaussiana.")
    parser.add_argument("--no-sharpen", action="store_true", help="Desativa o filtro de nitidez.")
    parser.add_argument("--sharpen-radius", type=float, default=1.2, help="Raio do filtro de nitidez.")
    parser.add_argument("--sharpen-amount", type=float, default=1.5, help="Intensidade da nitidez.")
    parser.add_argument("--safe-path", type=Path, help="Arquivo ou diretório SAFE já baixado.")
    parser.add_argument("--log-level", default="INFO", help="Nível de log (DEBUG, INFO, WARNING, ...).")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> None:
    args = parse_args(argv)
    log_level = getattr(logging, str(args.log_level).upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(levelname)s %(message)s")

    start_date, end_date = _resolve_dates(args)
    cloud_tuple = tuple(int(v) for v in args.cloud)  # type: ignore[arg-type]
    service = WorkflowService()
    result = service.run_date_range(
        start=start_date,
        end=end_date,
        aoi_geojson=args.geojson.expanduser().resolve(),
        cloud=cloud_tuple,  # type: ignore[arg-type]
        indices=args.indices,
        upsample=max(args.upsample, 1.0),
        smooth_radius=max(args.smooth_radius, 0.0),
        sharpen=not args.no_sharpen,
        sharpen_radius=args.sharpen_radius,
        sharpen_amount=args.sharpen_amount,
        tiles=args.tiles,
        padding=args.padding,
        safe_path=args.safe_path.expanduser().resolve() if args.safe_path else None,
    )

    print(f"Produto: {result.product_title}")
    if result.maps:
        print("Mapas gerados:")
        for path in result.maps:
            print(f" - {path}")
    if result.indices:
        print("Índices disponíveis:")
        for name, path in sorted(result.indices.items()):
            print(f" - {name}: {path}")


if __name__ == "__main__":
    main()
