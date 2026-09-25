import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
import runtime_paths


class RuntimePathsTests(unittest.TestCase):
    def test_source_keeps_project_data(self):
        with patch.dict(os.environ, {'ZHUYI_V1_DATA': ''}), patch.object(sys, 'frozen', False, create=True):
            self.assertEqual(runtime_paths.data_directory(), runtime_paths.ROOT / 'data')

    def test_packaged_windows_uses_user_data(self):
        with patch.dict(os.environ, {'ZHUYI_V1_DATA': '', 'LOCALAPPDATA': str(Path.home() / 'example-local')}), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'win32'):
            self.assertEqual(runtime_paths.data_directory(), Path.home() / 'example-local' / 'Zhuyi' / 'v1')

    def test_packaged_mac_uses_application_support(self):
        with patch.dict(os.environ, {'ZHUYI_V1_DATA': ''}), patch.object(sys, 'frozen', True, create=True), patch.object(sys, 'platform', 'darwin'):
            self.assertEqual(runtime_paths.data_directory(), Path.home() / 'Library' / 'Application Support' / 'Zhuyi' / 'v1')

    def test_explicit_archive_overrides_packaging(self):
        with patch.dict(os.environ, {'ZHUYI_V1_DATA': '~/example-archive'}), patch.object(sys, 'frozen', True, create=True):
            self.assertEqual(runtime_paths.data_directory(), (Path.home() / 'example-archive').resolve())

