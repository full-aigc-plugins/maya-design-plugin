"""Startup integration for studio-style Maya deployment."""

from __future__ import absolute_import

import traceback


PLUGIN_NAME = "jimeng_maya_uploader_plugin.py"


def autoload():
    """Load the plug-in during Maya startup so artists only see the menu."""
    try:
        import maya.cmds as cmds

        if cmds.about(batch=True):
            return

        if not cmds.pluginInfo(PLUGIN_NAME, query=True, loaded=True):
            cmds.loadPlugin(PLUGIN_NAME, quiet=True)
    except Exception:
        try:
            import maya.cmds as cmds

            cmds.warning(
                "Jimeng uploader startup failed:\n{0}".format(traceback.format_exc())
            )
        except Exception:
            pass

