"""Registry de bancas: nome → adapter.

O pipeline resolve ``job["banca"]`` por aqui — adicionar uma banca =
implementar ``bancas.base.BancaAdapter`` e registrar em ``BANCAS``.
"""

from __future__ import annotations

from .base import BancaAdapter
from .cebraspe import adapter as _cebraspe
from .fcc import adapter as _fcc
from .fgv import adapter as _fgv

BANCAS: dict[str, BancaAdapter] = {
    "cebraspe": _cebraspe,
    "fcc": _fcc,
    "fgv": _fgv,
}


def get_adapter(name: str) -> BancaAdapter:
    try:
        return BANCAS[name.lower()]
    except KeyError:
        raise ValueError(
            f"banca {name!r} desconhecida — registradas: {', '.join(BANCAS)}"
        ) from None
