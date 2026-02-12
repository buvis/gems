from .console.console import console, logging_to_console


def __getattr__(name: str) -> type:
    if name == "JiraAdapter":
        from .jira.jira import JiraAdapter

        return JiraAdapter
    if name == "ShellAdapter":
        from .shell.shell import ShellAdapter

        return ShellAdapter
    if name == "UvAdapter":
        from .uv.uv import UvAdapter

        return UvAdapter
    if name == "UvToolManager":
        from .uv.uv_tool import UvToolManager

        return UvToolManager
    if name == "OutlookLocalAdapter":
        import os

        if os.name == "nt":
            from .outlook_local.outlook_local import OutlookLocalAdapter

            return OutlookLocalAdapter
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = [
    "JiraAdapter",
    "ShellAdapter",
    "UvAdapter",
    "UvToolManager",
    "console",
    "logging_to_console",
]
