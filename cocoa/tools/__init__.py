import inspect

from . import system_tools


def iter_tools():
    """Yield every function in system_tools ending with '_tool' (cocoa-mcp convention)."""
    for name, obj in inspect.getmembers(system_tools, inspect.isfunction):
        if name.endswith("_tool"):
            yield obj
