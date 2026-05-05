"""Phase A smoke test — proves the package is importable end-to-end."""

from __future__ import annotations

import poe2_rpc
import poe2_rpc.application
import poe2_rpc.domain
import poe2_rpc.infrastructure


def test_package_importable() -> None:
    assert hasattr(poe2_rpc, "__version__")
    assert isinstance(poe2_rpc.__version__, str)
    assert poe2_rpc.__version__.count(".") == 2


def test_subpackages_importable() -> None:
    assert poe2_rpc.domain.__doc__ is not None
    assert poe2_rpc.application.__doc__ is not None
    assert poe2_rpc.infrastructure.__doc__ is not None
