"""Hermetic in-memory stand-in for `maya.cmds`.

The fake records every call so tests can assert read-only behavior. Mutation
helpers raise :class:`MutationForbiddenError` so any bridge code that tries to
change Maya state fails loudly in tests instead of silently corrupting scenes.

Only the surface used by the scene inspection bridge is implemented. New cmds
must be added explicitly; doing so will break any test that depends on the
existing surface until it is updated, which is the intended safety net.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any


class MutationForbiddenError(AssertionError):
    """Raised when code attempts to mutate Maya state through the fake."""


@dataclass
class FakeCmds:
    """In-memory Maya.cmds replacement."""

    cameras: tuple[str, ...] = ()
    playback_range: tuple[int, int] = (1, 240)
    current_time: int = 1
    resolution: tuple[int, int] = (1920, 1080)
    model_panels: tuple[str, ...] = ()
    display_modes: dict[str, str] = field(default_factory=dict)
    materials: tuple[str, ...] = ()
    references: tuple[str, ...] = ()
    namespaces: tuple[str, ...] = ()
    callbacks: tuple[str, ...] = ()
    unknown_plugins: tuple[str, ...] = ()
    selection: tuple[str, ...] = ()
    loaded_plugins: tuple[str, ...] = ()
    calls: list[tuple[str, tuple[Any, ...], dict[str, Any]]] = field(default_factory=list)

    # --- read-only surface --------------------------------------------------

    def listCameras(self) -> list[str]:  # noqa: N802 - Maya cmds naming
        self._record("listCameras")
        return list(self.cameras)

    def playbackRange(self) -> list[float]:  # noqa: N802
        self._record("playbackRange")
        return [float(self.playback_range[0]), float(self.playback_range[1])]

    def currentTime(self, *args: Any, **kwargs: Any) -> int:  # noqa: N802
        if args or kwargs:
            raise MutationForbiddenError("currentTime() is read-only in this fake")
        self._record("currentTime")
        return self.current_time

    def getAttr(self, attr: str, **kwargs: Any) -> Any:  # noqa: N802
        self._record("getAttr", (attr,), kwargs)
        if attr.endswith(".resolutionWidth"):
            return self.resolution[0]
        if attr.endswith(".resolutionHeight"):
            return self.resolution[1]
        if attr.endswith(".displayMode"):
            panel = attr.split(".", 1)[0]
            return self.display_modes.get(panel, "smoothShaded")
        return None

    def ls(self, *args: Any, **kwargs: Any) -> list[str]:  # noqa: N802
        self._record("ls", args, kwargs)
        if kwargs.get("type") == "camera" or "cameras" in args:
            return list(self.cameras)
        if kwargs.get("type") == "material" or "materials" in args:
            return list(self.materials)
        if kwargs.get("references") or "references" in args:
            return list(self.references)
        if kwargs.get("namespace") or "namespaces" in args:
            return list(self.namespaces)
        if "callbacks" in args:
            return list(self.callbacks)
        if kwargs.get("type") == "unknownPlugin":
            return list(self.unknown_plugins)
        return []

    def getPanel(self, *args: Any, **kwargs: Any) -> list[str]:  # noqa: N802
        self._record("getPanel", args, kwargs)
        if args and args[0] == "-type":
            return ["modelPanel"]
        return list(self.model_panels)

    def pluginInfo(self, plugin: str, *args: Any, **kwargs: Any) -> bool:  # noqa: N802
        self._record("pluginInfo", (plugin,) + args, kwargs)
        if kwargs.get("query") and kwargs.get("loaded"):
            return plugin in self.loaded_plugins
        raise MutationForbiddenError("pluginInfo() supports only query/loaded in this fake")

    def ls_sl(self, *args: Any, **kwargs: Any) -> list[str]:  # noqa: N802
        self._record("ls_sl", args, kwargs)
        return list(self.selection)

    # --- forbidden mutators (used to assert no-mutation) --------------------

    def select(self, *args: Any, **kwargs: Any) -> None:  # noqa: N802
        raise MutationForbiddenError("select() mutates selection; not allowed during inspection")

    def loadPlugin(self, *args: Any, **kwargs: Any) -> None:  # noqa: N802
        raise MutationForbiddenError("loadPlugin() is forbidden during inspection")

    def currentTime_set(self, value: int) -> None:  # noqa: N802
        raise MutationForbiddenError("currentTime set is forbidden during inspection")

    # --- helpers ------------------------------------------------------------

    def _record(self, name: str, args: Sequence[Any] = (), kwargs: dict[str, Any] | None = None) -> None:
        self.calls.append((name, tuple(args), dict(kwargs or {})))

    def mutating_calls(self) -> list[str]:
        # Anything not in this set is suspect. Add to the set only after a bridge
        # audit confirms it is truly read-only.
        read_only = {
            "listCameras",
            "playbackRange",
            "currentTime",
            "getAttr",
            "ls",
            "getPanel",
            "pluginInfo",
            "ls_sl",
        }
        return [name for name, *_ in self.calls if name not in read_only]


def install_fake(module_name: str = "maya.cmds") -> FakeCmds:
    """Register a fresh FakeCmds instance as `maya.cmds` and return it.

    The bridge imports `maya.cmds` and calls methods on it directly. We install
    a module whose attributes point at a single FakeCmds instance so the bridge
    code under test remains identical to production.
    """

    import sys
    import types

    fake = FakeCmds()
    pkg = types.ModuleType("maya")
    mod = types.ModuleType(module_name)
    for name in dir(fake):
        if name.startswith("_"):
            continue
        setattr(mod, name, getattr(fake, name))
    pkg.cmds = mod
    sys.modules["maya"] = pkg
    sys.modules[module_name] = mod
    return fake


def uninstall_fake() -> None:
    """Remove the fake modules so subsequent imports get the real one (or none)."""

    import sys

    sys.modules.pop("maya.cmds", None)
    sys.modules.pop("maya", None)


__all__ = ["FakeCmds", "MutationForbiddenError", "install_fake", "uninstall_fake"]
