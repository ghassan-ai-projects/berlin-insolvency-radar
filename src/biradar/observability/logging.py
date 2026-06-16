"""Lightweight logging helpers for biradar."""

import logging


def get_logger(name: str) -> logging.Logger:
    """Return a standard library logger with a stable local setup."""
    return logging.getLogger(name)
