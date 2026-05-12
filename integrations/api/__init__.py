"""Minimal HTTP ingress for the vertical slice (thin boundary)."""

from integrations.api.app import app, create_app

__all__ = ("app", "create_app")
