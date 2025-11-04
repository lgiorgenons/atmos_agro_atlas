"""Quick helper to check Sentinel credential env vars.

Usage (after ativar o venv com as variáveis setadas):

    python scripts/check_sentinel_credentials.py

It prints the username and masks the password length so you confirm that
both variables are carregadas para o processo atual.
"""

from __future__ import annotations

import os


def main() -> None:
    username = os.getenv("SENTINEL_USERNAME")
    password = os.getenv("SENTINEL_PASSWORD")

    if not username:
        print("SENTINEL_USERNAME: **NÃO DEFINIDO**")
    else:
        print(f"SENTINEL_USERNAME: {username}")

    if not password:
        print("SENTINEL_PASSWORD: **NÃO DEFINIDO**")
    else:
        masked = "*" * len(password)
        print(f"SENTINEL_PASSWORD: {masked} (len={len(password)})")


if __name__ == "__main__":
    main()

