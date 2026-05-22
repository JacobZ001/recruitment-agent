"""Backward-compatible shim; canonical runtime holder is ``modules.recruitment.runtime``."""

from modules.recruitment.runtime import DevResetResult, VerticalSliceApiRuntime

__all__ = ("DevResetResult", "VerticalSliceApiRuntime")
