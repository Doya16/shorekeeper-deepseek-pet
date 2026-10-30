"""Selectable window/tray identity; shipped resources remain program-owned."""
from PySide6.QtGui import QIcon

def icon_path(root,style='badged'):
    path=root/'resources/icons/app.ico' if style=='badged' else root/'assets/shorekeeper.ico'
    return path if path.is_file() else root/'assets/shorekeeper.ico'

def application_icon(root,style='badged'):
    return QIcon(str(icon_path(root,style)))
