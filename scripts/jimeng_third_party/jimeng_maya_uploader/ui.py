"""Maya UI for creating Jimeng/Dreamina import links from preview videos."""

from __future__ import absolute_import

import os
import sys
import traceback
import webbrowser

import maya.cmds as cmds

from . import dcc_config, playblast, settings, upload_bridge, variant
from .maya_qt import QtCore, QtGui, QtWidgets, Signal, maya_main_window


WINDOW_OBJECT_NAME = "jimengMayaUploaderWindow"
SHELF_BUTTON_NAME = "jimengMayaUploaderShelfButton"
FALLBACK_ORIGINAL_WIDTH = 1280.0
FALLBACK_ORIGINAL_HEIGHT = 720.0
EXPORT_SYNC_INTERVAL_MS = 3000
WINDOW_TITLE_INDENT = "        "
_WINDOW = None


class UploadThread(QtCore.QThread):
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, video_path, prompt, target_url, max_file_size=None, parent=None):
        super(UploadThread, self).__init__(parent)
        self.video_path = video_path
        self.prompt = prompt
        self.target_url = target_url
        self.max_file_size = max_file_size

    def run(self):
        try:
            result = upload_bridge.start_local_bridge(
                self.video_path,
                self.prompt,
                self.target_url,
                max_file_size=self.max_file_size,
            )
            self.finished.emit(result)
        except Exception:
            self.failed.emit(traceback.format_exc())


class JimengUploaderWindow(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super(JimengUploaderWindow, self).__init__(parent or maya_main_window())
        self.setObjectName(WINDOW_OBJECT_NAME)
        self.setWindowTitle(WINDOW_TITLE_INDENT + variant.APP_NAME)
        self._configure_window_flags()
        self.setMinimumWidth(680)
        self._upload_thread = None
        self._busy = False
        self._config = settings.load_config()
        self._camera_cache = {}
        self._active_camera_key = ""
        self._syncing_camera = False
        self._last_dcc_config = dcc_config.fallback_config()
        self._current_export_cache_camera = False
        self._playblast_mode = True
        self._redirect_url = ""
        self._link_signature = ""
        self._task_state = "IDLE"
        self._error_message = ""
        self._export_sync_timer = None
        self._manual_frame_range = False
        self._build_ui()
        self._load_initial_values()
        self._start_export_sync_timer()

    def _configure_window_flags(self):
        self.setWindowModality(QtCore.Qt.NonModal)
        if sys.platform != "darwin":
            return
        flags = self.windowFlags()
        flags &= ~QtCore.Qt.WindowType_Mask
        flags |= QtCore.Qt.Tool
        flags &= ~QtCore.Qt.WindowContextHelpButtonHint
        self.setWindowFlags(flags)
        always_show_tool_window = getattr(QtCore.Qt, "WA_MacAlwaysShowToolWindow", None)
        if always_show_tool_window is not None:
            self.setAttribute(always_show_tool_window, True)

    def _build_ui(self):
        self.setStyleSheet(_STYLE)
        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        panel = QtWidgets.QFrame()
        panel.setObjectName("panel")
        panel.setFocusPolicy(QtCore.Qt.StrongFocus)
        self._focus_sink = panel
        root.addWidget(panel)

        content = QtWidgets.QVBoxLayout(panel)
        content.setContentsMargins(28, 26, 28, 26)
        content.setSpacing(12)
        content.setAlignment(QtCore.Qt.AlignTop)

        self.camera_mode_button = QtWidgets.QPushButton(variant.text("mode_camera_display"))
        self.camera_mode_button.setToolTip(variant.text("mode_camera"))
        self.local_mode_button = QtWidgets.QPushButton(variant.text("mode_local_display"))
        self.local_mode_button.setToolTip(variant.text("mode_local"))
        for button in (self.camera_mode_button, self.local_mode_button):
            button.setCheckable(True)
            button.setMinimumHeight(36)
        self.camera_mode_button.setChecked(True)

        self.mode_group = QtWidgets.QButtonGroup(self)
        self.mode_group.setExclusive(True)
        self.mode_group.addButton(self.camera_mode_button)
        self.mode_group.addButton(self.local_mode_button)
        self.camera_mode_button.clicked.connect(lambda _checked=False: self._set_mode(True))
        self.local_mode_button.clicked.connect(lambda _checked=False: self._set_mode(False))

        segment = QtWidgets.QFrame()
        segment.setObjectName("segment")
        segment_layout = QtWidgets.QHBoxLayout(segment)
        segment_layout.setContentsMargins(2, 2, 2, 2)
        segment_layout.setSpacing(0)
        segment_layout.addWidget(self.camera_mode_button, 1)
        segment_layout.addWidget(self.local_mode_button, 1)

        self.upload_limit_label = _hint_label("")
        self.upload_mode_group_widget = _compact_stack(
            _form_row(variant.text("video_upload_method"), segment),
            _hint_row(self.upload_limit_label),
        )
        content.addWidget(self.upload_mode_group_widget)

        self.camera_combo = QtWidgets.QComboBox()
        self.camera_combo.setObjectName("cameraCombo")
        _setup_combo_box(self.camera_combo)
        self.clear_camera_button = _ClearButton()
        self.clear_camera_button.setObjectName("cameraClearButton")
        self.clear_camera_button.setFixedSize(34, 34)
        self.clear_camera_button.clicked.connect(self._clear_camera)
        camera_field = QtWidgets.QFrame()
        camera_field.setObjectName("cameraField")
        camera_field.setFixedHeight(36)
        camera_field_layout = QtWidgets.QHBoxLayout(camera_field)
        camera_field_layout.setContentsMargins(0, 0, 4, 0)
        camera_field_layout.setSpacing(0)
        camera_field_layout.addWidget(self.camera_combo, 1)
        camera_field_layout.addWidget(self.clear_camera_button, 0, QtCore.Qt.AlignVCenter)
        camera_row = QtWidgets.QHBoxLayout()
        camera_row.setContentsMargins(0, 0, 0, 0)
        camera_row.setSpacing(0)
        camera_row.addWidget(camera_field, 1)
        self.camera_row_widget = _form_row(variant.text("camera"), _layout_widget(camera_row))

        self.resolution_combo = QtWidgets.QComboBox()
        _setup_combo_box(self.resolution_combo)
        self.resolution_combo.addItems(["360P", "480P", "720P", "1080P", "Origin"])
        self.resolution_combo.setCurrentText(dcc_config.DEFAULT_RESOLUTION_LABEL)
        resolution_row = QtWidgets.QHBoxLayout()
        resolution_row.setContentsMargins(0, 0, 0, 0)
        resolution_row.setSpacing(8)
        resolution_row.addWidget(self.resolution_combo, 1)
        self.resolution_row_widget = _form_row(variant.text("resolution"), _layout_widget(resolution_row))

        start, end = playblast.selected_camera_frame_range(playblast.active_camera())
        self.start_spin = QtWidgets.QSpinBox()
        self.start_spin.setObjectName("frameSpin")
        self.start_spin.setRange(-100000, 100000)
        self.start_spin.setValue(start)
        self.start_spin.setMinimumHeight(36)
        self.end_spin = QtWidgets.QSpinBox()
        self.end_spin.setObjectName("frameSpin")
        self.end_spin.setRange(-100000, 100000)
        self.end_spin.setValue(end)
        self.end_spin.setMinimumHeight(36)
        frame_row = QtWidgets.QHBoxLayout()
        frame_row.setContentsMargins(0, 0, 0, 0)
        frame_row.setSpacing(8)
        frame_row.addWidget(_frame_spin_field("Start", self.start_spin), 1)
        frame_row.addWidget(_frame_spin_field("End", self.end_spin), 1)
        self.frame_row_widget = _form_row(variant.text("frame_range"), _layout_widget(frame_row))

        self.max_frame_label = _hint_label("")
        self.max_frame_row_widget = _hint_row(self.max_frame_label)
        self.frame_group_widget = _compact_stack(self.frame_row_widget, self.max_frame_row_widget)

        self.default_params_button = _DisclosureButton(variant.text("default_params"))
        self.default_params_button.setChecked(True)
        self.default_params_button.setObjectName("linkButton")
        self.default_params_button.setFixedWidth(_LABEL_WIDTH)
        self.default_params_button.setMinimumHeight(30)
        self.default_params_button.setToolTip(variant.text("default_params").replace("\n", " "))
        self.default_params_button.clicked.connect(self._sync_default_params)
        params_row = QtWidgets.QHBoxLayout()
        params_row.setContentsMargins(0, 0, 0, 0)
        params_row.addWidget(self.default_params_button)
        params_row.addStretch()
        self.default_params_button_widget = _layout_widget(params_row)

        self.fps_value_label = _plain_value("24fps")
        self.format_value_label = _plain_value("mp4 h264")
        self.preview_value_label = _plain_value(variant.text("preview_mode_auto"))

        self.output_dir_edit = QtWidgets.QLineEdit()
        self.output_dir_edit.setPlaceholderText(variant.text("output_placeholder"))
        output_browse_button = QtWidgets.QPushButton(variant.text("browse"))
        output_browse_button.clicked.connect(self._browse_output_dir)
        output_row = QtWidgets.QHBoxLayout()
        output_row.setContentsMargins(0, 0, 0, 0)
        output_row.setSpacing(8)
        output_row.addWidget(self.output_dir_edit, 1)
        output_row.addWidget(output_browse_button)
        self.output_row_widget = _form_row(variant.text("output_to"), _layout_widget(output_row))

        default_params = QtWidgets.QVBoxLayout()
        default_params.setContentsMargins(_LABEL_WIDTH + 14, 0, 0, 0)
        default_params.setSpacing(12)
        default_params.addWidget(_param_row(variant.text("frame_rate"), self.fps_value_label))
        default_params.addWidget(_param_row(variant.text("format"), self.format_value_label))
        default_params.addWidget(_param_row(variant.text("preview_mode"), self.preview_value_label))
        self.default_params_widget = _layout_widget(default_params)

        content.addWidget(self.camera_row_widget)
        content.addWidget(self.resolution_row_widget)
        content.addWidget(self.frame_group_widget)
        content.addWidget(self.default_params_button_widget)
        content.addWidget(self.default_params_widget)
        content.addWidget(self.output_row_widget)

        self.video_path_edit = QtWidgets.QLineEdit()
        self.video_path_edit.setPlaceholderText(variant.text("choose_placeholder"))
        browse_button = QtWidgets.QPushButton(variant.text("browse"))
        browse_button.clicked.connect(self._browse_video)
        video_row = QtWidgets.QHBoxLayout()
        video_row.setContentsMargins(0, 0, 0, 0)
        video_row.setSpacing(8)
        video_row.addWidget(self.video_path_edit, 1)
        video_row.addWidget(browse_button)
        self.video_row_widget = _form_row(variant.text("choose_video_file"), _layout_widget(video_row))
        content.addWidget(self.video_row_widget)

        buttons = QtWidgets.QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        buttons.setSpacing(8)
        self.primary_button = QtWidgets.QPushButton(variant.text("render"))
        self.primary_button.setObjectName("primaryButton")
        self.primary_button.setMinimumHeight(42)
        self.primary_button.clicked.connect(self._run_primary_action)
        self.open_link_button = QtWidgets.QPushButton(variant.text("preview"))
        self.open_link_button.setObjectName("secondaryButton")
        self.open_link_button.setFixedHeight(42)
        self.open_link_button.setEnabled(False)
        self.open_link_button.clicked.connect(self._preview_video)
        buttons.addWidget(self.primary_button, 1)
        buttons.addWidget(self.open_link_button)
        content.addLayout(buttons)

        self.min_frame_hint_label = _button_hint_label("")
        self.min_frame_hint_label.setVisible(False)
        content.addWidget(self.min_frame_hint_label)

        self.error_label = QtWidgets.QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.setVisible(False)
        content.addWidget(self.error_label)

        self.link_panel = QtWidgets.QFrame()
        self.link_panel.setObjectName("linkPanel")
        link_panel_layout = QtWidgets.QVBoxLayout(self.link_panel)
        link_panel_layout.setContentsMargins(10, 10, 10, 10)
        link_panel_layout.setSpacing(10)
        self.link_edit = QtWidgets.QLineEdit()
        self.link_edit.setReadOnly(True)
        link_panel_layout.addWidget(_form_row(variant.text("dreamina_link"), self.link_edit))
        self.link_open_button = QtWidgets.QPushButton(variant.text("open_link"))
        self.link_open_button.setObjectName("secondaryButton")
        self.link_open_button.setMinimumHeight(36)
        self.link_open_button.clicked.connect(self._open_redirect_url)
        link_panel_layout.addWidget(self.link_open_button)
        self.link_panel.setVisible(False)
        content.addWidget(self.link_panel)

        self.status_label = QtWidgets.QLabel("")
        self.status_label.setObjectName("statusLabel")
        self.status_label.setWordWrap(True)
        self.status_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.status_label.setVisible(False)
        content.addWidget(self.status_label)

        self.log_box = QtWidgets.QPlainTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setFixedHeight(120)
        self.log_box.setVisible(False)
        content.addWidget(self.log_box)

        self.video_path_edit.textChanged.connect(self._sync_action_buttons)
        self.video_path_edit.textChanged.connect(lambda _text="": self._invalidate_result())
        self.output_dir_edit.textChanged.connect(lambda _text="": self._invalidate_result())
        self.resolution_combo.currentIndexChanged.connect(lambda _index=0: self._invalidate_result())
        self.start_spin.valueChanged.connect(self._on_frame_range_edited)
        self.end_spin.valueChanged.connect(self._on_frame_range_edited)
        self.camera_combo.currentIndexChanged.connect(self._on_camera_changed)

    def _load_initial_values(self):
        self.output_dir_edit.setText(self._config.get("output_dir", ""))
        self.video_path_edit.setText(self._config.get("video_path", ""))
        self.resolution_combo.setCurrentText(dcc_config.DEFAULT_RESOLUTION_LABEL)
        self._refresh_cameras()
        self._load_protocol_defaults()
        self._sync_user_export_parameters()
        self._sync_default_params()
        self._sync_mode()

    def _save_values(self):
        settings.save_config(
            {
                "output_dir": self.output_dir_edit.text().strip(),
                "video_path": self.video_path_edit.text().strip(),
            }
        )

    def _input_signature(self):
        if self._is_playblast_mode():
            return "|".join(
                [
                    "camera",
                    self._current_camera_key(),
                    self._selected_resolution_key(),
                    str(int(self.start_spin.value())),
                    str(int(self.end_spin.value())),
                    os.path.abspath(self.output_dir_edit.text().strip() or ""),
                    str(int(self._original_resolution()[0])),
                    str(int(self._original_resolution()[1])),
                ]
            )
        return "|".join(["local", os.path.abspath(self.video_path_edit.text().strip() or "")])

    def _link_is_current(self):
        return bool(
            self._redirect_url
            and self._task_state == "SUCCESS"
            and self._link_signature
            and self._link_signature == self._input_signature()
        )

    def _invalidate_result(self):
        if self._busy:
            return
        self._redirect_url = ""
        self._link_signature = ""
        self._task_state = "IDLE"
        self._error_message = ""
        self._sync_result_panels()
        self._sync_action_buttons()

    def _set_task_state(self, state, error_message=""):
        self._task_state = state
        self._error_message = error_message or ""
        self._sync_result_panels()

    def _sync_result_panels(self):
        has_link = self._link_is_current()
        self.link_edit.setText(self._redirect_url if has_link else "")
        layout_changed = self._set_panel_visible(self.link_panel, has_link)
        self.link_open_button.setEnabled(has_link)
        self.open_link_button.setEnabled(self._preview_video_ready() and not self._busy)
        show_error = bool(self._task_state == "FAILED" and self._error_message)
        error_text = self._error_message if show_error else ""
        error_text_changed = self.error_label.text() != error_text
        self.error_label.setText(error_text)
        layout_changed = self._set_panel_visible(self.error_label, show_error) or (
            layout_changed or (show_error and error_text_changed)
        )
        self._adjust_size_for_layout_change(layout_changed)

    def _set_panel_visible(self, widget, visible):
        visible = bool(visible)
        was_visible = not widget.isHidden()
        if was_visible == visible:
            return False
        widget.setVisible(visible)
        widget.updateGeometry()
        return True

    def _adjust_size_for_layout_change(self, changed):
        if changed and self.isVisible():
            self._resize_to_content_height()
            QtCore.QTimer.singleShot(0, self._resize_to_content_height)

    def _resize_to_content_height(self):
        if self.isHidden():
            return
        layout = self.layout()
        if layout is not None:
            layout.activate()
        hint = self.sizeHint()
        width = max(self.minimumWidth(), self.width(), hint.width())
        height = max(self.minimumHeight(), hint.height())
        self.resize(width, height)

    def _load_protocol_defaults(self):
        try:
            config = dcc_config.fetch_dcc_protocol_config(settings.DEFAULT_TARGET_URL)
            dcc_config.validate_export_protocol(config)
        except Exception as exc:
            config = dcc_config.fallback_config(str(exc))
        self._sync_protocol_labels(config)

    def _sync_protocol_labels(self, config):
        self._last_dcc_config = config
        protocol = dcc_config.video_protocol(config)
        fps = int(protocol.get("fps") or dcc_config.DEFAULT_FPS)
        container = str(protocol.get("container_format") or dcc_config.DEFAULT_CONTAINER_FORMAT)
        codec = str(protocol.get("codec") or dcc_config.DEFAULT_CODEC)
        file_size = int(protocol.get("file_size") or dcc_config.DEFAULT_FILE_SIZE)
        max_frame_num = int(protocol.get("max_frame_num") or dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS)
        self.fps_value_label.setText("{0}fps".format(fps))
        self.format_value_label.setText("{0} {1}".format(container, codec))
        self.preview_value_label.setText(variant.text("preview_mode_auto"))
        upload_limit_text = variant.text("upload_limit", size=_compact_file_size(file_size))
        max_frame_text = variant.text("max_frames", count=max_frame_num)
        self.upload_limit_label.setText(upload_limit_text)
        self.max_frame_label.setText(max_frame_text)

    def _sync_default_params(self):
        expanded = self.default_params_button.isChecked()
        self.default_params_button.update()
        self._adjust_size_for_layout_change(self._set_panel_visible(self.default_params_widget, expanded))

    def _is_playblast_mode(self):
        return self._playblast_mode

    def _set_mode(self, playblast_mode):
        self._playblast_mode = bool(playblast_mode)
        self._invalidate_result()
        self._sync_mode()

    def _sync_mode(self):
        playblast_mode = self._is_playblast_mode()
        self.camera_mode_button.setChecked(playblast_mode)
        self.local_mode_button.setChecked(not playblast_mode)
        layout_changed = False
        layout_changed = self._set_panel_visible(self.camera_row_widget, playblast_mode) or layout_changed
        layout_changed = self._set_panel_visible(self.resolution_row_widget, playblast_mode) or layout_changed
        layout_changed = self._set_panel_visible(self.frame_group_widget, playblast_mode) or layout_changed
        layout_changed = self._set_panel_visible(self.default_params_button_widget, playblast_mode) or layout_changed
        layout_changed = (
            self._set_panel_visible(
                self.default_params_widget,
                playblast_mode and self.default_params_button.isChecked(),
            )
            or layout_changed
        )
        layout_changed = self._set_panel_visible(self.output_row_widget, playblast_mode) or layout_changed
        layout_changed = self._set_panel_visible(self.video_row_widget, not playblast_mode) or layout_changed
        self.primary_button.setText(variant.text("render"))
        self._sync_action_buttons()
        self._adjust_size_for_layout_change(layout_changed)

    def _fetch_dcc_config(self):
        self._set_stage("config", "progress", "Fetching DCC protocol config")
        config = dcc_config.fetch_dcc_protocol_config(settings.DEFAULT_TARGET_URL)
        dcc_config.validate_export_protocol(config)
        self._sync_protocol_labels(config)
        if config.get("source") == "fallback":
            self._set_stage("config", "fallback", config.get("warning") or "Using default DCC protocol")
        else:
            self._set_stage("config", "success", "Loaded DCC protocol config")
        return config

    def _sync_action_buttons(self):
        playblast_mode = self._is_playblast_mode()
        self.primary_button.setText(
            variant.text("rendering" if playblast_mode else "generating")
            if self._busy
            else variant.text("render")
        )
        if self._busy:
            self.primary_button.setEnabled(False)
            self.open_link_button.setEnabled(False)
            self._sync_min_frame_hint(False)
            return

        frame_too_short = self._frame_range_too_short()
        playblast_ready = (
            bool(self._current_camera_key())
            and not frame_too_short
        )
        self.primary_button.setEnabled(playblast_ready if playblast_mode else True)
        self._sync_min_frame_hint(playblast_mode and frame_too_short)
        self._sync_result_panels()

    def _selected_resolution_key(self):
        return dcc_config.normalize_resolution_key(
            self.resolution_combo.currentText() or dcc_config.DEFAULT_RESOLUTION_KEY
        )

    def _resolution_display_text(self, key):
        labels = {
            "360p": "360P",
            "480p": "480P",
            "720p": "720P",
            "1080p": "1080P",
            "origin": "Origin",
        }
        return labels.get(
            dcc_config.normalize_resolution_key(key),
            dcc_config.DEFAULT_RESOLUTION_LABEL,
        )

    def _positive_scene_attr(self, attr_name, fallback):
        try:
            value = float(cmds.getAttr(attr_name))
        except Exception:
            return fallback
        return value if value > 0 else fallback

    def _original_resolution(self):
        percent = self._positive_scene_attr("defaultResolution.percent", 100.0)
        return (
            self._positive_scene_attr("defaultResolution.width", FALLBACK_ORIGINAL_WIDTH) * percent / 100.0,
            self._positive_scene_attr("defaultResolution.height", FALLBACK_ORIGINAL_HEIGHT) * percent / 100.0,
        )

    def _target_short_edge(self):
        spec = dcc_config.export_resolution_spec(self._selected_resolution_key())
        if spec.get("origin"):
            return 0.0
        short_edge = float(spec.get("short_edge") or 0.0)
        if short_edge > 0:
            return short_edge
        width = float(spec.get("width") or FALLBACK_ORIGINAL_WIDTH)
        height = float(spec.get("height") or FALLBACK_ORIGINAL_HEIGHT)
        return max(2.0, min(width, height))

    def _even_dimension(self, value):
        try:
            parsed = int(float(value))
        except Exception:
            parsed = 2
        if parsed % 2:
            parsed -= 1
        return max(2, parsed)

    def _protocol_frame_limit(self):
        protocol = dcc_config.video_protocol(self._last_dcc_config)
        try:
            max_frame_num = int(
                protocol.get("max_frame_num")
                or dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS
            )
        except Exception:
            max_frame_num = dcc_config.DEFAULT_DURATION * dcc_config.DEFAULT_FPS
        return max(1, max_frame_num)

    def _min_frame_limit(self):
        protocol = dcc_config.video_protocol(self._last_dcc_config)
        try:
            min_frame_num = int(protocol.get("min_frame_num") or dcc_config.DEFAULT_MIN_FRAME_NUM)
        except Exception:
            min_frame_num = dcc_config.DEFAULT_MIN_FRAME_NUM
        return max(1, min_frame_num)

    def _selected_frame_count(self):
        return max(0, int(self.end_spin.value()) - int(self.start_spin.value()) + 1)

    def _frame_range_too_short(self):
        return self._selected_frame_count() < self._min_frame_limit()

    def _sync_min_frame_hint(self, show=None):
        if show is None:
            show = self._is_playblast_mode() and self._frame_range_too_short()
        self.min_frame_hint_label.setText(
            variant.text(
                "min_frames_hint",
                count=self._min_frame_limit(),
                seconds=dcc_config.DEFAULT_MIN_DURATION_SECONDS,
            )
            if show
            else ""
        )
        self._adjust_size_for_layout_change(self._set_panel_visible(self.min_frame_hint_label, bool(show)))

    def _clamp_frame_range(self, start, end):
        start = int(start)
        end = int(end)
        if start > end:
            end = start
        limit = self._protocol_frame_limit()
        if end - start + 1 > limit:
            end = start + limit - 1
        return start, end

    def _current_export_frame_range(self):
        camera = self._current_camera_key() or playblast.active_camera()
        start, end = playblast.selected_camera_frame_range(camera)
        return self._clamp_frame_range(start, end)

    def _refresh_cameras(self):
        current = self._current_camera_key()
        self._syncing_camera = True
        self.camera_combo.clear()
        self.camera_combo.addItem(variant.text("choose_placeholder"), "")
        cameras = playblast.list_cameras()
        active = playblast.active_camera()
        for camera in cameras:
            self.camera_combo.addItem(_camera_display_name(camera), camera)
        if active:
            idx = self.camera_combo.findData(active)
            if idx >= 0:
                self.camera_combo.setCurrentIndex(idx)
        if current:
            idx = self.camera_combo.findData(current)
            if idx >= 0:
                self.camera_combo.setCurrentIndex(idx)
        self._syncing_camera = False
        self._on_camera_changed()

    def _current_camera_key(self):
        data = self.camera_combo.currentData()
        return data if isinstance(data, str) else ""

    def _clear_camera(self):
        self.camera_combo.setCurrentIndex(0)

    def _on_frame_range_edited(self, _value=0):
        self._manual_frame_range = True
        self._invalidate_result()

    def _sync_user_export_parameters(self, force=False):
        if self._manual_frame_range and not force:
            return False
        changed = False
        try:
            start, end = self._current_export_frame_range()
            changed = (
                int(self.start_spin.value()) != int(start)
                or int(self.end_spin.value()) != int(end)
            )
            self.start_spin.blockSignals(True)
            self.end_spin.blockSignals(True)
            self.start_spin.setValue(int(start))
            self.end_spin.setValue(int(end))
        finally:
            self.start_spin.blockSignals(False)
            self.end_spin.blockSignals(False)
        return changed

    def _start_export_sync_timer(self):
        self._export_sync_timer = QtCore.QTimer(self)
        self._export_sync_timer.setInterval(EXPORT_SYNC_INTERVAL_MS)
        self._export_sync_timer.timeout.connect(self._poll_export_parameters)
        self._export_sync_timer.start()

    def _poll_export_parameters(self):
        if self._busy or not self._is_playblast_mode():
            return
        try:
            old_signature = self._link_signature
            self._sync_user_export_parameters()
            if old_signature and old_signature != self._input_signature():
                self._invalidate_result()
            else:
                self._sync_result_panels()
        except Exception:
            pass

    def _on_camera_changed(self):
        if self._syncing_camera:
            return
        self._manual_frame_range = False
        self._sync_user_export_parameters(force=True)
        key = self._current_camera_key()
        self._active_camera_key = key
        cached = self._camera_cache.get(key) if key else None
        if isinstance(cached, dict):
            self._set_redirect_url(
                cached.get("redirect_url", "") or "",
                signature=cached.get("signature", "") or "",
            )
        else:
            self._set_redirect_url("")
        self._sync_action_buttons()

    def _store_current_camera_result(self):
        key = self._current_camera_key()
        if not key or not self._redirect_url:
            return
        self._active_camera_key = key
        self._camera_cache[key] = {
            "redirect_url": self._redirect_url,
            "signature": self._link_signature,
        }
        self._save_values()

    def _browse_video(self):
        filters = "Video Files (*.mp4 *.mov *.webm *.avi);;All Files (*)"
        try:
            path, _selected_filter = QtWidgets.QFileDialog.getOpenFileName(
                self,
                "Choose preview video",
                os.path.dirname(self.video_path_edit.text()) or os.path.expanduser("~"),
                filters,
            )
        finally:
            self._restore_front_after_native_dialog()
        if path:
            self.video_path_edit.setText(path)

    def _browse_output_dir(self):
        try:
            path = QtWidgets.QFileDialog.getExistingDirectory(
                self,
                "Choose playblast output directory",
                self.output_dir_edit.text() or settings.default_output_dir(),
            )
        finally:
            self._restore_front_after_native_dialog()
        if path:
            self.output_dir_edit.setText(path)

    def _run_primary_action(self):
        if self._is_playblast_mode():
            self._playblast_and_upload()
        else:
            self._upload_existing_video()

    def _upload_existing_video(self):
        try:
            self.log_box.clear()
            self._adjust_size_for_layout_change(self._set_panel_visible(self.log_box, False))
            config = self._fetch_dcc_config()
            video_path = self.video_path_edit.text().strip()
            if not self._validate_video_path(video_path):
                return
            self._set_task_state("RUNNING")
            self._set_stage("export", "success", "Using local file: {0}".format(video_path))
            self._start_upload(video_path, config, cache_camera=False)
        except Exception as exc:
            self._set_busy(False, "Export failed.")
            self._set_stage("failed", "error", str(exc))
            self._set_task_state("FAILED", _friendly_error("existing", exc, self._last_dcc_config))
            self._append_log(traceback.format_exc(), reveal=True)
            _maya_warning(str(exc))

    def _playblast_and_upload(self):
        try:
            self.log_box.clear()
            self._adjust_size_for_layout_change(self._set_panel_visible(self.log_box, False))
            if not self._current_camera_key():
                _maya_warning("Choose a camera before exporting to Dreamina.")
                return
            self._save_values()
            config = self._fetch_dcc_config()
            self._sync_user_export_parameters()
            start_frame = int(self.start_spin.value())
            end_frame = int(self.end_spin.value())
            dcc_config.validate_frame_range(config, start_frame, end_frame)
            self._set_task_state("RUNNING")
            self._set_busy(
                True,
                "Running Maya playblast: frames {0}-{1}...".format(
                    start_frame,
                    end_frame,
                ),
            )
            camera = self._current_camera_key()
            width, height = self._resolution(config)
            fps = int(dcc_config.video_protocol(config).get("fps") or dcc_config.DEFAULT_FPS)
            self._set_stage("export", "progress", "Running Playblast {0}x{1} @ {2}fps".format(width, height, fps))
            video_path = playblast.run_playblast(
                camera=camera,
                start_frame=start_frame,
                end_frame=end_frame,
                width=width,
                height=height,
                fps=fps,
                output_dir=self.output_dir_edit.text().strip() or None,
            )
            self.video_path_edit.setText(video_path)
            dcc_config.validate_file_size(video_path, config)
            self._set_stage(
                "export",
                "success",
                "Created {0} ({1})".format(video_path, dcc_config.format_bytes(os.path.getsize(video_path))),
            )
            self._start_upload(video_path, config, cache_camera=True)
        except dcc_config.DccConfigError as exc:
            self._set_busy(False, "Export failed.")
            self._set_stage("validate", "failed", str(exc))
            self._set_task_state("FAILED", _friendly_error("validate", exc, config if "config" in locals() else self._last_dcc_config))
            self._append_log(traceback.format_exc(), reveal=True)
            _maya_warning(str(exc))
        except Exception as exc:
            self._set_busy(False, "Playblast failed.")
            self._set_stage("failed", "error", str(exc))
            self._set_task_state("FAILED", _friendly_error("render", exc, config if "config" in locals() else self._last_dcc_config))
            self._append_log(traceback.format_exc(), reveal=True)
            _maya_warning(str(exc))

    def _start_upload(self, video_path, config, cache_camera=False):
        self._save_values()
        self._current_export_cache_camera = cache_camera
        self._set_redirect_url("")
        self._set_busy(True, "Starting local bridge and creating Jimeng link...")
        self._set_task_state("RUNNING")
        self._set_stage("bridge", "progress", "Starting local bridge")

        self._upload_thread = UploadThread(
            video_path=video_path,
            prompt=dcc_config.prompt_for_export(config, ""),
            target_url=settings.DEFAULT_TARGET_URL,
            max_file_size=dcc_config.video_protocol(config).get("file_size"),
            parent=self,
        )
        self._upload_thread.finished.connect(self._on_upload_finished)
        self._upload_thread.failed.connect(self._on_upload_failed)
        self._upload_thread.start()

    def _on_upload_finished(self, result):
        redirect_url = result.get("redirect_url") or ""
        self._set_redirect_url(redirect_url, signature=self._input_signature())
        self._set_busy(False, "Local bridge ready. Open or copy the Jimeng link.")
        self._set_stage("bridge", "success", "Dreamina link is ready")
        self._append_log(str(result))
        if result.get("status") == "ready" and redirect_url:
            self._set_task_state("SUCCESS")
            if self._current_export_cache_camera:
                self._store_current_camera_result()
            cmds.inViewMessage(
                amg="Jimeng uploader: local bridge link ready.",
                pos="topCenter",
                fade=True,
            )

    def _on_upload_failed(self, message):
        self._set_busy(False, "Local bridge failed.")
        self._set_stage("bridge", "failed", "Local bridge failed")
        self._set_task_state("FAILED", _friendly_error("bridge", message, self._last_dcc_config))
        self._append_log(message, reveal=True)
        self._copy_to_clipboard(self.video_path_edit.text().strip())
        _maya_warning("Local bridge failed. Video path copied for manual fallback.")

    def _validate_video_path(self, video_path):
        if not video_path:
            _maya_warning("Choose a video file first.")
            return False
        if not os.path.exists(video_path):
            _maya_warning("Video file does not exist: {0}".format(video_path))
            return False
        _, ext = os.path.splitext(video_path)
        if ext.lower() not in settings.SUPPORTED_VIDEO_EXTENSIONS:
            _maya_warning(
                "Unsupported video extension: {0}. Use mp4, mov, webm, or avi.".format(
                    ext
                )
            )
            return False
        return True

    def _set_redirect_url(self, url, signature=""):
        self._redirect_url = url or ""
        self._link_signature = signature or ""
        self._sync_result_panels()

    def _preview_video_path(self):
        return os.path.abspath(self.video_path_edit.text().strip() or "")

    def _preview_video_ready(self):
        path = self._preview_video_path()
        if not (path and os.path.exists(path)):
            return False
        if self._is_playblast_mode():
            return self._link_is_current()
        return True

    def _preview_video(self):
        path = self._preview_video_path()
        if not path or not os.path.exists(path):
            _maya_warning("No preview video is ready yet.")
            return
        try:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(path))
        except Exception:
            webbrowser.open("file://{0}".format(path), new=2)
        self._restore_front_after_native_dialog()

    def _open_redirect_url(self):
        if not self._link_is_current():
            _maya_warning("Create a Jimeng link first.")
            return

        try:
            protocol = dcc_config.video_protocol(self._last_dcc_config)
            result = upload_bridge.ensure_local_bridge(
                self._redirect_url,
                video_path=self._preview_video_path(),
                prompt=dcc_config.prompt_for_export(self._last_dcc_config, ""),
                target_url=settings.DEFAULT_TARGET_URL,
                max_file_size=protocol.get("file_size"),
            )
            redirect_url = result.get("redirect_url") or ""
            if not redirect_url:
                raise upload_bridge.UploadError("The refreshed Dreamina link is empty.")
            if result.get("restarted"):
                self._set_redirect_url(redirect_url, signature=self._input_signature())
                if self._is_playblast_mode():
                    self._store_current_camera_result()
                self._set_stage("bridge", "success", "Expired local bridge restarted")
                self._append_log(str(result))
            webbrowser.open(redirect_url, new=2)
        except Exception as exc:
            self._set_stage("bridge", "failed", str(exc))
            self._append_log(traceback.format_exc(), reveal=True)
            _maya_warning("Could not restart the local bridge: {0}".format(exc))
            return
        self._restore_front_after_native_dialog()

    def _resolution(self, _config):
        original_width, original_height = self._original_resolution()
        if self._selected_resolution_key() == "origin":
            return self._even_dimension(original_width), self._even_dimension(original_height)
        short_edge = self._target_short_edge()
        scale = 1.0
        if original_width > 0 and original_height > 0 and short_edge > 0:
            scale = min(1.0, short_edge / min(original_width, original_height))
        return (
            self._even_dimension(original_width * scale),
            self._even_dimension(original_height * scale),
        )

    def closeEvent(self, event):
        if self._export_sync_timer is not None:
            self._export_sync_timer.stop()
        QtWidgets.QDialog.closeEvent(self, event)

    def _set_busy(self, busy, message):
        self._busy = busy
        self._sync_action_buttons()
        self.status_label.setText("")
        self._adjust_size_for_layout_change(self._set_panel_visible(self.status_label, False))

    def _set_stage(self, stage, state, message):
        text = "[{0}] {1}: {2}".format(stage, state, message)
        self._append_log(text)
        return text

    def _append_log(self, message, reveal=False):
        self.log_box.appendPlainText(message)
        if reveal and os.environ.get("JIMENG_UPLOADER_SHOW_LOG") == "1":
            self._show_log()

    def _show_log(self):
        self._adjust_size_for_layout_change(self._set_panel_visible(self.log_box, True))

    def _restore_front_after_native_dialog(self):
        QtCore.QTimer.singleShot(0, self._raise_and_activate)

    def _raise_and_activate(self):
        if self.isHidden():
            return
        self.raise_()
        self.activateWindow()

    def _clear_input_focus(self):
        if self.isHidden():
            return
        focused = QtWidgets.QApplication.focusWidget()
        if focused is not None and self.isAncestorOf(focused):
            focused.clearFocus()
        self._focus_sink.setFocus(QtCore.Qt.OtherFocusReason)

    def _copy_to_clipboard(self, text):
        if not text:
            return
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(text)


def _compact_file_size(size):
    try:
        value = int(size)
    except Exception:
        value = dcc_config.DEFAULT_FILE_SIZE
    if value > 0 and value % (1024 * 1024) == 0:
        if getattr(variant, "LANGUAGE", "") == "en_us":
            return "{0} MB".format(value // (1024 * 1024))
        return "{0}M".format(value // (1024 * 1024))
    return dcc_config.format_bytes(value)


def _camera_display_name(camera):
    name = str(camera or "")
    return name.rsplit("|", 1)[-1] or name


def _friendly_error(stage, error, config):
    message = str(error).strip()
    protocol = dcc_config.video_protocol(config)
    file_size = _compact_file_size(protocol.get("file_size") or dcc_config.DEFAULT_FILE_SIZE)
    if "Exported file is too large" in message:
        return variant.text("error_file_size", size=file_size)
    if "shorter than DCC min_frame_num" in message:
        return variant.text(
            "min_frames_hint",
            count=protocol.get("min_frame_num") or dcc_config.DEFAULT_MIN_FRAME_NUM,
            seconds=dcc_config.DEFAULT_MIN_DURATION_SECONDS,
        )
    if stage == "bridge":
        return variant.text("error_bridge", reason=message)
    if stage == "existing":
        return variant.text("error_existing", reason=message)
    return variant.text("error_render", reason=message)


_LABEL_WIDTH = 104
_CONTROL_FONT_SIZE = 13
_COMBO_POPUP_ROW_HEIGHT = 24


class _NoMnemonicItemDelegate(QtWidgets.QStyledItemDelegate):
    def sizeHint(self, option, index):
        size = QtWidgets.QStyledItemDelegate.sizeHint(self, option, index)
        size.setHeight(max(size.height(), _COMBO_POPUP_ROW_HEIGHT))
        return size

    def paint(self, painter, option, index):
        item_option = QtWidgets.QStyleOptionViewItem(option)
        self.initStyleOption(item_option, index)
        widget = item_option.widget
        style = widget.style() if widget else QtWidgets.QApplication.style()
        style.drawPrimitive(QtWidgets.QStyle.PE_PanelItemViewItem, item_option, painter, widget)

        text_rect = style.subElementRect(QtWidgets.QStyle.SE_ItemViewItemText, item_option, widget)
        selected = bool(item_option.state & QtWidgets.QStyle.State_Selected)
        enabled = bool(item_option.state & QtWidgets.QStyle.State_Enabled)
        if not enabled:
            color_role = QtGui.QPalette.Disabled
            text_role = QtGui.QPalette.Text
        else:
            color_role = QtGui.QPalette.Active
            text_role = QtGui.QPalette.HighlightedText if selected else QtGui.QPalette.Text

        painter.save()
        painter.setPen(item_option.palette.color(color_role, text_role))
        painter.drawText(
            text_rect,
            QtCore.Qt.AlignLeft
            | QtCore.Qt.AlignVCenter
            | QtCore.Qt.TextSingleLine
            | QtCore.Qt.TextHideMnemonic,
            item_option.text,
        )
        painter.restore()


class _DisclosureButton(QtWidgets.QPushButton):
    def __init__(self, text, parent=None):
        super(_DisclosureButton, self).__init__(text, parent)
        self.setCheckable(True)

    def paintEvent(self, event):
        QtWidgets.QPushButton.paintEvent(self, event)
        rect = self.rect()
        center_x = rect.right() - 5
        center_y = rect.center().y()
        if "\n" in str(self.text() or ""):
            center_y = rect.top() + max(7, self.fontMetrics().lineSpacing() // 2 + 1)

        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor("#f2f2f2" if self.isEnabled() else "#8f8f8f"))
        if self.isChecked():
            points = [
                QtCore.QPoint(center_x - 5, center_y - 3),
                QtCore.QPoint(center_x + 5, center_y - 3),
                QtCore.QPoint(center_x, center_y + 4),
            ]
        else:
            points = [
                QtCore.QPoint(center_x - 3, center_y - 5),
                QtCore.QPoint(center_x - 3, center_y + 5),
                QtCore.QPoint(center_x + 4, center_y),
            ]
        painter.drawPolygon(QtGui.QPolygon(points))
        painter.end()


class _ClearButton(QtWidgets.QPushButton):
    def __init__(self, parent=None):
        super(_ClearButton, self).__init__("", parent)

    def paintEvent(self, event):
        QtWidgets.QPushButton.paintEvent(self, event)
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
        pen = QtGui.QPen(QtGui.QColor("#d8d8d8" if self.isEnabled() else "#8f8f8f"), 1.8)
        painter.setPen(pen)
        center = self.rect().center()
        span = 7
        painter.drawLine(center.x() - span, center.y() - span, center.x() + span, center.y() + span)
        painter.drawLine(center.x() + span, center.y() - span, center.x() - span, center.y() + span)
        painter.end()


def _setup_combo_box(combo):
    combo.setMinimumHeight(36)
    font = combo.font()
    font.setPointSize(_CONTROL_FONT_SIZE)
    combo.setFont(font)

    view = QtWidgets.QListView(combo)
    view.setObjectName("comboPopupView")
    view.setFont(font)
    view.setUniformItemSizes(True)
    view.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
    combo.setView(view)
    combo.setItemDelegate(_NoMnemonicItemDelegate(combo))


def _field_label(text):
    label = QtWidgets.QLabel(text)
    label.setObjectName("fieldLabel")
    label.setFixedWidth(_LABEL_WIDTH)
    label.setWordWrap(False)
    label.setToolTip(str(text or "").replace("\n", " "))
    label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
    return label


def _form_row(label_text, widget, compact=False):
    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    if compact:
        layout.addWidget(_field_label(label_text))
    else:
        layout.addWidget(_field_label(label_text))
    layout.addWidget(widget, 1)
    return _layout_widget(layout)


def _param_row(label_text, value_widget):
    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    label = QtWidgets.QLabel(label_text)
    label.setObjectName("paramLabel")
    label.setMinimumWidth(86)
    label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    layout.addWidget(label)
    layout.addWidget(value_widget)
    layout.addStretch()
    return _layout_widget(layout)


def _hint_label(text):
    label = QtWidgets.QLabel(text)
    label.setObjectName("hintLabel")
    label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    label.setFixedHeight(14)
    label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    return label


def _button_hint_label(text):
    label = QtWidgets.QLabel(text)
    label.setObjectName("hintLabel")
    label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
    label.setFixedHeight(16)
    label.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    return label


def _hint_row(label):
    layout = QtWidgets.QHBoxLayout()
    layout.setContentsMargins(_LABEL_WIDTH + 14, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(label)
    layout.addStretch()
    widget = _layout_widget(layout)
    widget.setFixedHeight(14)
    widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    return widget


def _compact_stack(*widgets):
    layout = QtWidgets.QVBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    for widget in widgets:
        layout.addWidget(widget)
    return _layout_widget(layout)


def _frame_spin_field(label_text, spin_box):
    frame = QtWidgets.QFrame()
    frame.setObjectName("frameSpinField")
    layout = QtWidgets.QHBoxLayout(frame)
    layout.setContentsMargins(10, 0, 0, 0)
    layout.setSpacing(4)
    if label_text:
        label = QtWidgets.QLabel(label_text)
        label.setObjectName("spinPrefixLabel")
        label.setFixedWidth(44)
        label.setAlignment(QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter)
        layout.addWidget(label)
    layout.addWidget(spin_box, 1)
    return frame


def _value_box(text):
    label = QtWidgets.QLabel(text)
    label.setObjectName("valueBox")
    label.setAlignment(QtCore.Qt.AlignVCenter | QtCore.Qt.AlignRight)
    label.setMinimumHeight(36)
    return label


def _plain_value(text):
    label = QtWidgets.QLabel(text)
    label.setObjectName("plainValue")
    return label


def _layout_widget(layout):
    widget = QtWidgets.QWidget()
    widget.setLayout(layout)
    widget.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Fixed)
    return widget


def _maya_warning(message):
    try:
        cmds.warning(message)
    except Exception:
        pass


def show_window():
    global _WINDOW
    for widget in QtWidgets.QApplication.topLevelWidgets():
        if widget.objectName() == WINDOW_OBJECT_NAME:
            widget.close()
            widget.deleteLater()
            break
    _WINDOW = JimengUploaderWindow()
    if _WINDOW.layout() is not None:
        _WINDOW.layout().activate()
    _WINDOW.adjustSize()
    _WINDOW.show()
    _WINDOW.raise_()
    _WINDOW.activateWindow()
    QtCore.QTimer.singleShot(0, _WINDOW._clear_input_focus)
    QtCore.QTimer.singleShot(80, _WINDOW._clear_input_focus)
    return _WINDOW


def install_shelf_button():
    shelf = "Custom"
    if not cmds.shelfLayout(shelf, exists=True):
        shelf = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)

    if cmds.shelfButton(SHELF_BUTTON_NAME, exists=True):
        cmds.deleteUI(SHELF_BUTTON_NAME)

    command = (
        "import importlib; "
        "import jimeng_maya_uploader.playblast as playblast; "
        "import jimeng_maya_uploader.upload_bridge as upload_bridge; "
        "import jimeng_maya_uploader.ui as ui; "
        "importlib.reload(playblast); "
        "importlib.reload(upload_bridge); "
        "importlib.reload(ui); "
        "ui.show_window()"
    )
    cmds.shelfButton(
        SHELF_BUTTON_NAME,
        parent=shelf,
        label="Seedance",
        annotation="Open Dreamina Seedance 2.5 Preview Render Upload",
        imageOverlayLabel="JM",
        command=command,
        sourceType="python",
    )
    cmds.inViewMessage(
        amg="Jimeng uploader shelf button installed.",
        pos="topCenter",
        fade=True,
    )


_STYLE = """
QDialog {
    background: #565656;
    color: #f2f2f2;
}
QFrame#panel {
    background: #3f3f3f;
    border-radius: 8px;
}
QLabel#fieldLabel {
    color: #f5f5f5;
    font-size: 14px;
}
QLabel#hintLabel {
    color: #8f8f8f;
    font-size: 10px;
    min-height: 13px;
}
QLabel#paramLabel {
    color: #f0f0f0;
    font-size: 13px;
}
QLabel#plainValue {
    color: #bdbdbd;
    font-size: 13px;
}
QLabel#valueBox {
    color: #f2f2f2;
    background: #4b4b4b;
    border: 1px solid #5c5c5c;
    border-radius: 6px;
    padding: 0 12px;
}
QLineEdit, QComboBox, QSpinBox {
    color: #f2f2f2;
    background: #4b4b4b;
    border: 1px solid #5c5c5c;
    border-radius: 6px;
    padding: 7px 10px;
    min-height: 22px;
    font-size: 13px;
}
QFrame#cameraField {
    background: #4b4b4b;
    border: 1px solid #5c5c5c;
    border-radius: 6px;
}
QComboBox#cameraCombo {
    background: transparent;
    border: 0;
    border-radius: 0;
    padding-left: 12px;
    padding-right: 4px;
}
QComboBox#cameraCombo::drop-down {
    width: 0;
    border: 0;
}
QPushButton#cameraClearButton {
    background: transparent;
    border: 0;
    border-radius: 4px;
    padding: 0;
}
QPushButton#cameraClearButton:hover {
    background: #565656;
}
QComboBox::drop-down {
    width: 28px;
    border: 0;
}
QListView#comboPopupView {
    color: #f2f2f2;
    background: #2f2f2f;
    border: 1px solid #4f4f4f;
    outline: 0;
    font-size: 13px;
}
QListView#comboPopupView::item {
    min-height: 24px;
    padding: 2px 10px;
}
QListView#comboPopupView::item:selected {
    background: #4b91a8;
    color: #ffffff;
}
QFrame#frameSpinField {
    color: #f2f2f2;
    background: #4b4b4b;
    border: 1px solid #5c5c5c;
    border-radius: 6px;
}
QLabel#spinPrefixLabel {
    color: #f2f2f2;
    font-size: 13px;
}
QSpinBox#frameSpin {
    color: #f2f2f2;
    background: transparent;
    border: 0;
    border-radius: 0;
    padding: 7px 4px;
    min-height: 22px;
}
QFrame#segment {
    background: #464646;
    border: 1px solid #5a5a5a;
    border-radius: 8px;
}
QFrame#segment QPushButton {
    color: #f2f2f2;
    background: transparent;
    border: 0;
    border-radius: 6px;
    padding: 8px 18px;
}
QFrame#segment QPushButton:checked {
    background: #4d7fbd;
}
QPushButton {
    color: #f2f2f2;
    background: #626262;
    border: 0;
    border-radius: 6px;
    padding: 8px 14px;
}
QPushButton:hover {
    background: #6c6c6c;
}
QPushButton:disabled {
    color: #8d8d8d;
    background: #555555;
}
QPushButton#primaryButton {
    background: #4d7fbd;
    font-size: 14px;
}
QPushButton#primaryButton:hover {
    background: #5a8dcd;
}
QPushButton#secondaryButton {
    background: #5a5a5a;
}
QPushButton#secondaryButton:hover:enabled {
    background: #5a8dcd;
}
QPushButton#secondaryButton:disabled {
    color: #9a9a9a;
    background: #5a5a5a;
}
QPushButton#iconButton {
    background: #4b4b4b;
    font-size: 16px;
}
QPushButton#linkButton {
    color: #f2f2f2;
    background: transparent;
    border: 0;
    padding-left: 0;
    padding-right: 22px;
    text-align: right;
}
QLabel#statusLabel {
    color: #f2f2f2;
    background: #333333;
    border-radius: 6px;
    padding: 10px;
}
QLabel#errorLabel {
    color: #f6a000;
    font-size: 12px;
}
QFrame#linkPanel {
    background: #343434;
    border-radius: 6px;
}
QPlainTextEdit {
    color: #d8d8d8;
    background: #2f2f2f;
    border: 1px solid #4a4a4a;
    border-radius: 6px;
}
"""
