"""Central logging configuration."""

import logging

from macmarket_trader.config import settings



def configure_logging() -> None:
    """Configure root logging once per process."""
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
