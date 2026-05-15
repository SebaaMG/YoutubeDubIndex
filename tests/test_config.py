from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app.config import Settings


class ConfigTests(unittest.TestCase):
    def test_runtime_and_data_paths_in_python_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            settings = Settings(project_root=root)
            self.assertEqual(settings.runtime_root, root)
            self.assertEqual(settings.resource_root, root)
            self.assertEqual(settings.executable_root, root)
            self.assertEqual(settings.data_dir, root / "data")
            self.assertEqual(settings.legacy_bundle_data_dir, root / "data")
            self.assertEqual(settings.bundled_node_path, root / "vendor" / "node" / "node.exe")

    def test_runtime_and_data_paths_in_frozen_mode_use_localappdata(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as local_appdata_dir:
            project_root = Path(project_dir)
            exe_root = project_root / "dist" / "YouTubeDubIndexer"
            resource_root = project_root / "build" / "_internal"

            with (
                patch("app.runtime.is_frozen", return_value=True),
                patch("app.runtime.executable_root", return_value=exe_root),
                patch("app.runtime.resource_root", return_value=resource_root),
                patch.dict("os.environ", {"LOCALAPPDATA": local_appdata_dir}, clear=False),
            ):
                settings = Settings(project_root=project_root)
                self.assertEqual(settings.runtime_root, Path(local_appdata_dir) / "YouTubeDubIndexer")
                self.assertEqual(settings.data_dir, Path(local_appdata_dir) / "YouTubeDubIndexer" / "data")
                self.assertEqual(settings.executable_root, exe_root)
                self.assertEqual(settings.legacy_bundle_data_dir, exe_root / "data")
                self.assertEqual(settings.resource_root, resource_root)


if __name__ == "__main__":
    unittest.main()
