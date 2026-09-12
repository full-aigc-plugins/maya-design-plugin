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
        if args:
            raise MutationForbiddenError("currentTime() with positional args mutates; not allowed")
        if kwargs.get("edit"):
            raise MutationForbiddenError("currentTime(edit=True) mutates; not allowed")
        self._record("currentTime", args, kwargs)
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


class FakePlayblastCmds(FakeCmds):
    """Fake that adds the mutable surface required by the Playblast bridge."""

    def currentTime(self, *args: Any, **kwargs: Any) -> int:  # noqa: N802
        # Override the inspection-only rule: the Playblast bridge may write.
        self._record("currentTime", args, kwargs)
        if kwargs.get("edit"):
            self.current_time = int(args[0]) if args else self.current_time
            return int(self.current_time)
        if args:
            raise MutationForbiddenError(
                "currentTime() with positional args and no edit flag is not allowed"
            )
        return self.current_time

    def __init__(self) -> None:
        super().__init__()
        self.active_camera: str | None = "camera1"
        self.active_panel: str | None = "modelPanel1"
        self.display_appearance: dict[str, str] = {"modelPanel1": "smoothShaded"}
        self.display_textures: dict[str, bool] = {"modelPanel1": True}
        self.renderer: str = "vp2"
        self.image_format: str = "png"
        self.playblast_files: dict[str, bytes] = {}
        self.next_playblast_id = 0
        self.injected_failure: str | None = None
        # Restoration audit:
        self.restoration_calls: list[str] = []

    # Snapshot surface -------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "selection": list(self.selection),
            "current_time": self.current_time,
            "playback_range": list(self.playback_range),
            "active_camera": self.active_camera,
            "active_panel": self.active_panel,
            "display_appearance": dict(self.display_appearance),
            "display_textures": dict(self.display_textures),
            "renderer": self.renderer,
            "image_format": self.image_format,
            "resolution": list(self.resolution),
        }

    def restore(self, snapshot: dict) -> None:
        self.selection = tuple(snapshot["selection"])
        self.current_time = snapshot["current_time"]
        self.playback_range = tuple(snapshot["playback_range"])
        self.active_camera = snapshot["active_camera"]
        self.active_panel = snapshot["active_panel"]
        self.display_appearance = dict(snapshot["display_appearance"])
        self.display_textures = dict(snapshot["display_textures"])
        self.renderer = snapshot["renderer"]
        self.image_format = snapshot["image_format"]
        self.resolution = tuple(snapshot["resolution"])
        self.restoration_calls.append("restored")

    # Mutation surface used by the bridge under test ------------------------

    def setAttr(self, attr: str, value: Any, **kwargs: Any) -> None:  # noqa: N802
        self._record("setAttr", (attr, value), kwargs)
        if attr.endswith(".resolutionWidth") or attr.endswith(".resolution.width"):
            self.resolution = (int(value), self.resolution[1])
        elif attr.endswith(".resolutionHeight") or attr.endswith(".resolution.height"):
            self.resolution = (self.resolution[0], int(value))
        elif attr.endswith("currentRenderer"):
            self.renderer = str(value)
        elif attr.endswith("imageFormat"):
            self.image_format = str(value)

    def playbackOptions(self, *args: Any, **kwargs: Any) -> Any:  # noqa: N802
        self._record("playbackOptions", args, kwargs)
        if kwargs.get("query"):
            if kwargs.get("minTime"):
                return self.playback_range[0]
            if kwargs.get("maxTime"):
                return self.playback_range[1]
            return list(self.playback_range)
        if kwargs.get("edit"):
            if "minTime" in kwargs:
                self.playback_range = (int(kwargs["minTime"]), self.playback_range[1])
            if "maxTime" in kwargs:
                self.playback_range = (self.playback_range[0], int(kwargs["maxTime"]))
        return None

    def optionVar(self, *args: Any, **kwargs: Any) -> Any:  # noqa: N802
        self._record("optionVar", args, kwargs)
        if kwargs.get("query"):
            name = str(args[0]) if args else kwargs.get("query")
            return None
        return None

    def modelPanel(self, panel: str, *args: Any, **kwargs: Any) -> Any:  # noqa: N802
        self._record("modelPanel", (panel,) + args, kwargs)
        if kwargs.get("query"):
            for key, default in (
                ("camera", None),
                ("displayAppearance", "smoothShaded"),
                ("displayTextures", True),
            ):
                if kwargs.get(key):
                    if key == "camera":
                        return self.active_camera
                    if key == "displayAppearance":
                        return self.display_appearance.get(panel, default)
                    if key == "displayTextures":
                        return self.display_textures.get(panel, default)
            return None
        if kwargs.get("edit"):
            for key, value in kwargs.items():
                if key == "edit":
                    continue
                if key == "camera":
                    self.active_camera = str(value)
                elif key == "displayAppearance":
                    self.display_appearance[panel] = str(value)
                elif key == "displayTextures":
                    self.display_textures[panel] = bool(value)
        return None

    def getPanel(self, *args: Any, **kwargs: Any) -> list[str]:  # noqa: N802
        self._record("getPanel", args, kwargs)
        if args and args[0] == "-type":
            return ["modelPanel"]
        if kwargs.get("typeOf"):
            return "modelPanel" if kwargs["typeOf"] == self.active_panel else "other"
        if kwargs.get("withFocus"):
            return self.active_panel
        if kwargs.get("type") == "modelPanel":
            return list(self.model_panels)
        return list(self.model_panels)

    def getAttr(self, attr: str, **kwargs: Any) -> Any:  # noqa: N802
        self._record("getAttr", (attr,), kwargs)
        leaf = attr.rsplit(".", 1)[-1]
        attr_lower = attr.lower()
        if leaf in ("resolutionWidth", "width") and "resolution" in attr_lower:
            return self.resolution[0]
        if leaf in ("resolutionHeight", "height") and "resolution" in attr_lower:
            return self.resolution[1]
        if leaf == "currentRenderer":
            return self.renderer
        if leaf == "imageFormat":
            return self.image_format
        if leaf == "displayMode":
            panel = attr.split(".", 1)[0]
            return self.display_modes.get(panel, "smoothShaded")
        return None

    def objExists(self, node: str) -> bool:  # noqa: N802
        self._record("objExists", (node,), {})
        if node in self.cameras or node == self.active_camera:
            return True
        return False

    def select(self, *args: Any, **kwargs: Any) -> None:  # noqa: N802
        self._record("select", args, kwargs)
        if kwargs.get("clear"):
            self.selection = ()
            return
        if kwargs.get("replace") and args:
            value = args[0]
            if isinstance(value, (list, tuple)):
                self.selection = tuple(str(item) for item in value if item)
            else:
                self.selection = (str(value),)
            return
        for value in args:
            if value:
                self.selection = (str(value),)

    def ls(self, *args: Any, **kwargs: Any) -> list[str]:  # noqa: N802
        self._record("ls", args, kwargs)
        if kwargs.get("selection"):
            return list(self.selection)
        if kwargs.get("long") and (args and args[0] == "selection"):
            return list(self.selection)
        if kwargs.get("type") == "camera":
            return list(self.cameras)
        return []

    def displayAppearance(self, panel: str, mode: str) -> None:  # noqa: N802
        self._record("displayAppearance", (panel, mode), {})
        self.display_appearance[panel] = mode

    def displayTextures(self, panel: str, enabled: bool) -> None:  # noqa: N802
        self._record("displayTextures", (panel, enabled), {})
        self.display_textures[panel] = bool(enabled)

    def setRenderGlobals(self, **kwargs: Any) -> None:  # noqa: N802
        self._record("setRenderGlobals", (), kwargs)
        if "currentRenderer" in kwargs:
            self.renderer = kwargs["currentRenderer"]

    def setAttr_with_render_globals(self, attr: str, value: str) -> None:  # noqa: N802
        self._record("setAttr", (attr, value), {})
        if attr.endswith(".imageFormat"):
            self.image_format = value

    def playblast(
        self,
        filename: str,
        *,
        format: str = "image",
        compression: str = "png",
        sequenceTime: int = 0,
        clearCache: bool = True,
        viewer: bool = False,
        showOrnaments: bool = True,
        offScreen: bool = True,
        width: int = 1920,
        height: int = 1080,
        camera: str | None = None,
        **kwargs: Any,
    ) -> list[str]:
        self._record("playblast", (filename,), {"format": format, "camera": camera})
        if self.injected_failure == "capture":
            raise RuntimeError("injected capture failure")
        self.next_playblast_id += 1
        path = f"{filename}.{self.next_playblast_id:04d}.{compression}"
        self.playblast_files[path] = b"playblast-bytes"
        return [path]

    def renameFile(self, src: str, dst: str) -> str:  # noqa: N802
        self._record("renameFile", (src, dst), {})
        if self.injected_failure == "conversion":
            raise RuntimeError("injected conversion failure")
        self.playblast_files[dst] = self.playblast_files.pop(src, b"")
        return dst

    def file(self, *, query: bool = False, fileName: str = "") -> str:  # noqa: N802
        self._record("file", (), {"query": query, "fileName": fileName})
        return fileName

    def set_active_camera(self, camera: str) -> None:
        self.active_camera = camera

    def inject_failure(self, stage: str | None) -> None:
        self.injected_failure = stage


def install_playblast_fake(module_name: str = "maya.cmds") -> FakePlayblastCmds:
    """Register a fresh FakePlayblastCmds as `maya.cmds`."""

    import sys
    import types

    fake = FakePlayblastCmds()
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


__all__ = [
    "FakeCmds",
    "FakePlayblastCmds",
    "MutationForbiddenError",
    "install_fake",
    "install_playblast_fake",
    "uninstall_fake",
]
