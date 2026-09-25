"""Resource and user-data locations shared by source and packaged editions."""
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent


def data_directory():
    override = os.environ.get('ZHUYI_V1_DATA')
    if override:
        return Path(override).expanduser().resolve()
    if not getattr(sys, 'frozen', False):
        return ROOT / 'data'
    if sys.platform == 'win32':
        return Path(os.environ.get('LOCALAPPDATA', Path.home() / 'AppData' / 'Local')) / 'Zhuyi' / 'v1'
    if sys.platform == 'darwin':
        return Path.home() / 'Library' / 'Application Support' / 'Zhuyi' / 'v1'
    return Path.home() / '.local' / 'share' / 'Zhuyi' / 'v1'
