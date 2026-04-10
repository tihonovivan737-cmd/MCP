from __future__ import annotations

import logging
import sys


def configure_logging(level: int = logging.INFO) -> None:
    if logging.getLogger().handlers:
        return
    h = logging.StreamHandler(sys.stderr)
    h.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(h)
