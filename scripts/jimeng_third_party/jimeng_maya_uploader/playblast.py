"""Viewport preview playblast utilities for Maya."""

from __future__ import absolute_import

import datetime
import os
import platform

import maya.cmds as cmds

from . import settings, upload_bridge


class PlayblastError(RuntimeError):
    pass


DEFAULT_SHADER_NAMES = set(["lambert1", "particleCloud1"])
TEXTURE_NODE_TYPES = set(
    [
        "file",
        "aiImage",
        "psdFileTex",
        "layeredTexture",
        "checker",
        "cloth",
        "fractal",
        "grid",
        "mountain",
        "noise",
        "ramp",
        "stencil",
        "water",
        "wood",
        "bump2d",
        "bump3d",
    ]
)


def list_cameras():
    cameras = []
    for shape in cmds.ls(type="camera", long=True) or []:
        parents = cmds.listRelatives(shape, parent=True, fullPath=True) or []
        cameras.append(parents[0] if parents else shape)
    return cameras


def active_camera():
    panel = cmds.getPanel(withFocus=True)
    if panel and cmds.getPanel(typeOf=panel) == "modelPanel":
        camera = cmds.modelEditor(panel, query=True, camera=True)
        if camera:
            return _camera_transform(camera)

    panels = cmds.getPanel(type="modelPanel") or []
    for panel in panels:
        camera = cmds.modelEditor(panel, query=True, camera=True)
        if camera:
            return _camera_transform(camera)

    cameras = list_cameras()
    return cameras[0] if cameras else None


def _is_model_panel(panel):
    if not panel:
        return False
    try:
        return cmds.getPanel(typeOf=panel) == "modelPanel"
    except Exception:
        return False


def _visible_model_panels():
    try:
        panels = cmds.getPanel(visiblePanels=True) or []
    except Exception:
        panels = []
    return [panel for panel in panels if _is_model_panel(panel)]


def _panel_camera(panel):
    try:
        return cmds.modelEditor(panel, query=True, camera=True)
    except Exception:
        return None


def active_model_panel(camera=None):
    panel = cmds.getPanel(withFocus=True)
    if _is_model_panel(panel):
        return panel

    visible_panels = _visible_model_panels()
    if camera:
        for panel in visible_panels:
            if _same_camera(_panel_camera(panel), camera):
                return panel
    if visible_panels:
        return visible_panels[0]

    try:
        panels = cmds.getPanel(type="modelPanel") or []
    except Exception:
        panels = []
    if camera:
        for panel in panels:
            if _same_camera(_panel_camera(panel), camera):
                return panel
    return panels[0] if panels else None


def playback_range():
    start = cmds.playbackOptions(query=True, minTime=True)
    end = cmds.playbackOptions(query=True, maxTime=True)
    return int(start), int(end)


_CUSTOM_FRAME_START_KEYS = (
    "frame_start",
    "start_frame",
    "startFrame",
    "shot_start",
    "shotStart",
    "shot_frame_start",
)
_CUSTOM_FRAME_END_KEYS = (
    "frame_end",
    "end_frame",
    "endFrame",
    "shot_end",
    "shotEnd",
    "shot_frame_end",
)


def selected_camera_frame_range(camera):
    camera = _camera_transform(camera)
    targets = _camera_targets(camera)

    for target in targets:
        custom_range = _custom_frame_range(target)
        if custom_range:
            return custom_range

    shot_range = _sequencer_shot_frame_range(camera)
    if shot_range:
        return shot_range

    return playback_range()


def _camera_transform(camera):
    if not camera:
        return camera
    matches = cmds.ls(camera, long=True) or []
    if matches:
        camera = matches[0]
    if not cmds.objExists(camera):
        return camera
    if cmds.nodeType(camera) == "camera":
        parents = cmds.listRelatives(camera, parent=True, fullPath=True) or []
        return parents[0] if parents else camera
    shapes = cmds.listRelatives(camera, shapes=True, fullPath=True) or []
    for shape in shapes:
        if cmds.nodeType(shape) == "camera":
            return camera
    return camera


def _camera_targets(camera):
    targets = []
    transform = _camera_transform(camera)
    if transform and cmds.objExists(transform):
        targets.append(transform)
        shapes = cmds.listRelatives(transform, shapes=True, fullPath=True) or []
        for shape in shapes:
            if cmds.nodeType(shape) == "camera":
                targets.append(shape)
    return targets


def _long_name(node):
    if not node:
        return ""
    try:
        transform = _camera_transform(node)
        matches = cmds.ls(transform, long=True) or []
        return matches[0] if matches else str(transform or node)
    except Exception:
        return str(node or "")


def _same_camera(left, right):
    left_long = _long_name(left)
    right_long = _long_name(right)
    if not left_long or not right_long:
        return False
    return left_long == right_long or left_long.rsplit("|", 1)[-1] == right_long.rsplit("|", 1)[-1]


def _numeric_attr(target, keys):
    if not target or not cmds.objExists(target):
        return None
    lookup = {key.lower(): key for key in keys}
    try:
        attrs = cmds.listAttr(target) or []
    except Exception:
        attrs = []

    for attr in attrs:
        expected = lookup.get(str(attr).lower())
        if not expected:
            continue
        try:
            value = cmds.getAttr("{0}.{1}".format(target, attr))
            if isinstance(value, (list, tuple)):
                value = value[0] if value else None
            if isinstance(value, (list, tuple)):
                value = value[0] if value else None
            return float(value)
        except Exception:
            pass
    return None


def _custom_frame_range(target):
    start = _numeric_attr(target, _CUSTOM_FRAME_START_KEYS)
    end = _numeric_attr(target, _CUSTOM_FRAME_END_KEYS)
    if start is None or end is None:
        return None
    if start > end:
        start, end = end, start
    return int(round(start)), int(round(end))


def _query_shot_time(shot, flag):
    try:
        value = cmds.shot(shot, query=True, **{flag: True})
        if isinstance(value, (list, tuple)):
            value = value[0] if value else None
        return float(value)
    except Exception:
        return None


def _sequencer_shot_frame_range(camera):
    if not camera:
        return None
    ranges = []
    for shot in cmds.ls(type="shot") or []:
        try:
            shot_camera = cmds.shot(shot, query=True, currentCamera=True)
        except Exception:
            shot_camera = None
        if not _same_camera(shot_camera, camera):
            continue

        start = _query_shot_time(shot, "sequenceStartTime")
        end = _query_shot_time(shot, "sequenceEndTime")
        if start is None or end is None:
            start = _query_shot_time(shot, "startTime")
            end = _query_shot_time(shot, "endTime")
        if start is None or end is None:
            continue
        if start > end:
            start, end = end, start
        ranges.append((start, end))

    if not ranges:
        return None
    return int(round(min(item[0] for item in ranges))), int(round(max(item[1] for item in ranges)))


def _safe_query_model_editor(panel, flag):
    try:
        return cmds.modelEditor(panel, query=True, **{flag: True})
    except Exception:
        return None


def _safe_edit_model_editor(panel, **kwargs):
    for key, value in kwargs.items():
        try:
            cmds.modelEditor(panel, edit=True, **{key: value})
        except Exception:
            pass


def _short_node_name(node):
    name = str(node or "")
    if "." in name:
        name = name.split(".", 1)[0]
    if "|" in name:
        name = name.rsplit("|", 1)[-1]
    return name


def _safe_node_type(node):
    try:
        return cmds.nodeType(node)
    except Exception:
        return ""


def _attribute_exists(node, attr):
    try:
        return cmds.attributeQuery(attr, node=node, exists=True)
    except Exception:
        return False


def _get_attr_values(node, attr):
    if not _attribute_exists(node, attr):
        return None
    try:
        value = cmds.getAttr("{0}.{1}".format(node, attr))
    except Exception:
        return None
    if isinstance(value, (list, tuple)) and value:
        value = value[0]
    if isinstance(value, (list, tuple)):
        return tuple(float(item) for item in value)
    try:
        return (float(value),)
    except Exception:
        return None


def _values_close(left, right, tolerance=0.025):
    if left is None:
        return True
    count = min(len(left), len(right))
    return all(abs(float(left[index]) - float(right[index])) <= tolerance for index in range(count))


def _connected_source_nodes(node):
    try:
        return cmds.listConnections(node, source=True, destination=False, plugs=False) or []
    except Exception:
        return []


def _has_connected_texture(node, visited=None):
    if not node:
        return False
    visited = visited or set()
    node_name = _short_node_name(node)
    if node_name in visited:
        return False
    visited.add(node_name)

    node_type = _safe_node_type(node)
    if node_type in TEXTURE_NODE_TYPES:
        return True

    for source in _connected_source_nodes(node):
        if _has_connected_texture(source, visited):
            return True
    return False


def _shader_material_preview_reason(shader):
    if not shader:
        return ""
    if _has_connected_texture(shader):
        return "texture connection"

    shader_type = _safe_node_type(shader)
    if shader_type in ("standardSurface", "aiStandardSurface"):
        color_defaults = (("baseColor", (0.8, 0.8, 0.8)), ("emissionColor", (0.0, 0.0, 0.0)))
    else:
        color_defaults = (("color", (0.5, 0.5, 0.5)), ("incandescence", (0.0, 0.0, 0.0)))

    for attr, default in color_defaults:
        if not _values_close(_get_attr_values(shader, attr), default):
            return "non-default {0}".format(attr)

    for attr, default in (
        ("metalness", (0.0,)),
        ("metallic", (0.0,)),
        ("transparency", (0.0, 0.0, 0.0)),
        ("alpha", (1.0,)),
    ):
        if not _values_close(_get_attr_values(shader, attr), default):
            return "non-default {0}".format(attr)

    if _short_node_name(shader) not in DEFAULT_SHADER_NAMES and shader_type not in (
        "lambert",
        "standardSurface",
        "aiStandardSurface",
    ):
        return "custom shader node"

    return ""


def mesh_material_preview_reason(mesh):
    try:
        if cmds.getAttr("{0}.intermediateObject".format(mesh)):
            return ""
    except Exception:
        pass

    try:
        shading_engines = cmds.listConnections(mesh, type="shadingEngine") or []
    except Exception:
        shading_engines = []

    for shading_engine in shading_engines:
        if _has_connected_texture(shading_engine):
            return "texture connection"
        try:
            shaders = cmds.listConnections(
                "{0}.surfaceShader".format(shading_engine),
                source=True,
                destination=False,
                plugs=False,
            ) or []
        except Exception:
            shaders = []
        for shader in shaders:
            reason = _shader_material_preview_reason(shader)
            if reason:
                return reason

    return ""


def scene_has_material_preview():
    for mesh in cmds.ls(type="mesh", long=True) or []:
        reason = mesh_material_preview_reason(mesh)
        if reason:
            return True
    return False


def preview_mode_for_scene():
    return "material" if scene_has_material_preview() else "solid"


class ViewportPreviewState(object):
    """Temporarily tune the viewport for plugin preview playblast."""

    FLAGS = (
        "camera",
        "grid",
        "nurbsCurves",
        "nurbsSurfaces",
        "polymeshes",
        "subdivSurfaces",
        "planes",
        "lights",
        "cameras",
        "joints",
        "ikHandles",
        "deformers",
        "dynamics",
        "fluids",
        "hairSystems",
        "follicles",
        "nCloths",
        "nParticles",
        "locators",
        "dimensions",
        "handles",
        "pivots",
        "textures",
        "strokes",
        "manipulators",
        "headsUpDisplay",
        "selectionHiliteDisplay",
        "wireframeOnShaded",
        "useDefaultMaterial",
        "displayAppearance",
    )

    def __init__(self, panel, camera, use_materials=False):
        self.panel = panel
        self.camera = camera
        self.use_materials = bool(use_materials)
        self.values = {}
        self.selection = []
        self.current_time = None

    def __enter__(self):
        self.selection = cmds.ls(selection=True, long=True) or []
        self.current_time = cmds.currentTime(query=True)

        for flag in self.FLAGS:
            self.values[flag] = _safe_query_model_editor(self.panel, flag)

        if self.camera:
            _safe_edit_model_editor(self.panel, camera=self.camera)

        _safe_edit_model_editor(
            self.panel,
            grid=False,
            nurbsCurves=False,
            joints=False,
            ikHandles=False,
            locators=False,
            dimensions=False,
            handles=False,
            pivots=False,
            lights=False,
            cameras=False,
            textures=self.use_materials,
            strokes=False,
            manipulators=False,
            headsUpDisplay=False,
            selectionHiliteDisplay=False,
            wireframeOnShaded=False,
            useDefaultMaterial=not self.use_materials,
            displayAppearance="smoothShaded",
        )
        return self

    def __exit__(self, exc_type, exc, traceback):
        restore = {
            key: value for key, value in self.values.items() if value is not None
        }
        _safe_edit_model_editor(self.panel, **restore)

        if self.current_time is not None:
            try:
                cmds.currentTime(self.current_time, edit=True)
            except Exception:
                pass

        try:
            cmds.select(clear=True)
            if self.selection:
                cmds.select(self.selection, replace=True)
        except Exception:
            pass
        return False


ViewportWhiteModelState = ViewportPreviewState


def make_output_base(output_dir, camera, preview_mode="solid"):
    if not os.path.isdir(output_dir):
        os.makedirs(output_dir)
    camera_name = os.path.basename(camera or "camera").replace("|", "_")
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = "material_preview" if preview_mode == "material" else "white_model"
    return os.path.join(output_dir, "{0}_{1}_{2}".format(prefix, camera_name, stamp))


def _movie_format_and_extension():
    system = platform.system().lower()
    if system == "darwin":
        return "avfoundation", ".mov"
    if system == "windows":
        return "avi", ".avi"
    return "qt", ".mov"


def _playblast_compression(movie_format):
    env_value = os.environ.get("JIMENG_UPLOADER_PLAYBLAST_COMPRESSION")
    if env_value is not None:
        value = env_value.strip()
        return value or None

    system = platform.system().lower()
    if system == "darwin" and movie_format == "avfoundation":
        return "H.264"
    return None


def _playblast_argument_variants(playblast_args):
    variants = [dict(playblast_args)]

    if playblast_args.get("offScreenViewportUpdate"):
        without_viewport_update = dict(playblast_args)
        without_viewport_update.pop("offScreenViewportUpdate", None)
        variants.append(without_viewport_update)

    if playblast_args.get("offScreen"):
        onscreen = dict(playblast_args)
        onscreen.pop("offScreen", None)
        onscreen.pop("offScreenViewportUpdate", None)
        variants.append(onscreen)

    return variants


def _run_maya_playblast(playblast_args, compression=None):
    errors = []
    for capture_args in _playblast_argument_variants(playblast_args):
        if compression:
            compressed_args = dict(capture_args)
            compressed_args["compression"] = compression
            try:
                return cmds.playblast(**compressed_args)
            except Exception as exc:
                errors.append("compression '{0}': {1}".format(compression, exc))

        try:
            return cmds.playblast(**capture_args)
        except Exception as exc:
            errors.append("default compression: {0}".format(exc))

    raise PlayblastError(
        "Playblast failed for all supported viewport capture modes.\n{0}".format(
            "\n".join(errors)
        )
    )


def run_playblast(
    camera,
    start_frame,
    end_frame,
    width,
    height,
    fps=24,
    output_dir=None,
    convert_to_mp4=True,
):
    camera = _camera_transform(camera or active_camera())
    if not camera or not cmds.objExists(camera):
        raise PlayblastError("No valid camera was found for playblast.")

    panel = active_model_panel(camera)
    if not panel:
        raise PlayblastError("No Maya model panel is available for playblast.")

    output_dir = output_dir or settings.default_output_dir()
    preview_mode = preview_mode_for_scene()
    output_base = make_output_base(output_dir, camera, preview_mode)
    movie_format, extension = _movie_format_and_extension()
    compression = _playblast_compression(movie_format)
    intermediate = output_base + extension

    with ViewportPreviewState(panel, camera, use_materials=preview_mode == "material"):
        try:
            cmds.currentTime(start_frame, edit=True)
        except Exception:
            pass
        try:
            cmds.refresh(force=True)
        except Exception:
            pass
        result = _run_maya_playblast(
            {
                "filename": intermediate,
                "format": movie_format,
                "editorPanelName": panel,
                "offScreen": True,
                "offScreenViewportUpdate": True,
                "startTime": start_frame,
                "endTime": end_frame,
                "widthHeight": (int(width), int(height)),
                "percent": 100,
                "quality": 90,
                "viewer": False,
                "showOrnaments": False,
                "forceOverwrite": True,
                "clearCache": True,
            },
            compression=compression,
        )

    result_path = _normalize_playblast_result(result, intermediate)
    if not os.path.exists(result_path):
        raise PlayblastError("Playblast did not create a movie: {0}".format(result_path))

    if convert_to_mp4:
        mp4_path = output_base + ".mp4"
        converted = convert_movie_to_mp4(result_path, mp4_path, width, height, fps)
        if converted:
            return converted
        raise PlayblastError(
            "Playblast was created, but MP4 conversion failed: {0}".format(
                result_path
            )
        )

    return result_path


def _normalize_playblast_result(result, expected_path):
    if isinstance(result, (list, tuple)) and result:
        result = result[0]
    if isinstance(result, str) and os.path.exists(result):
        return result
    if os.path.exists(expected_path):
        return expected_path
    root, ext = os.path.splitext(expected_path)
    for candidate in (root + ext.lower(), root + ext.upper()):
        if os.path.exists(candidate):
            return candidate
    return expected_path


def convert_movie_to_mp4(source_path, target_path, width, height, fps=24):
    even_width = int(width) if int(width) % 2 == 0 else int(width) - 1
    even_height = int(height) if int(height) % 2 == 0 else int(height) - 1
    vf = "scale={0}:{1}:flags=lanczos:out_range=tv,format=yuv420p".format(
        even_width,
        even_height,
    )
    arguments = [
        "-y",
        "-i",
        source_path,
        "-vf",
        vf,
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-r",
        str(int(fps) or 24),
        "-pix_fmt",
        "yuv420p",
        "-color_range",
        "tv",
        "-tag:v",
        "avc1",
        "-movflags",
        "+faststart",
        target_path,
    ]

    try:
        upload_bridge.run_ffmpeg(arguments, output_path=target_path)
    except upload_bridge.UploadError as exc:
        raise PlayblastError(
            "Playblast MP4 conversion failed.\n{0}".format(exc)
        )

    return target_path
