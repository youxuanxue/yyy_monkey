"""Gradio GUI 模块."""

from importlib import import_module


def __getattr__(name):
    if name in {"create_app", "launch_app"}:
        module = import_module("media_publisher.gui.app")
        value = getattr(module, name)
        globals()[name] = value
        return value
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["create_app", "launch_app"]
