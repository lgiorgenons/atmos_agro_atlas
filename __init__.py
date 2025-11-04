"""Compatibilidade durante a migração para o novo pacote `core`.

Todo o processamento orientado a objetos agora vive no pacote `core`.
Este módulo apenas reexporta o conteúdo do novo core para manter
imports transitórios funcionais enquanto atualizamos o restante do código.
"""

from core import *  # type: ignore  # noqa: F401,F403
from core import __all__ as _core_all  # type: ignore

__all__ = list(_core_all)
