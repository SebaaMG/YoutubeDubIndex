from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from . import runtime


@dataclass(frozen=True)
class Settings:
    project_root: Path
    host: str = "127.0.0.1"
    port: int = 8876
    db_filename: str = "dub_index_desktop.db"
    app_version: str = "2026.05.17.1"
    app_title: str = ""
    startup_test_video_id: str = "dQw4w9WgXcQ"
    inspect_workers: int = 4
    inspect_retry_attempts: int = 2
    inspect_stale_days: int = 30
    dub_classifier_version: int = 9
    metadata_backfill_limit: int = 1000
    startup_metadata_backfill_limit: int = 250
    metadata_backfill_workers: int = 2
    default_search_candidates: int = 1000
    default_channel_candidates: int = 1000
    app_storage_dirname: str = "YouTubeDubIndexer"
    discovery_seed_batch: int = 2
    discovery_inspect_batch: int = 12
    discovery_seed_candidate_limit: int = 50
    discovery_loop_interval_seconds: int = 45
    starter_pack_version: str = "v3"
    content_pool_version: str = "v2"
    update_manifest_url: str = ""

    @property
    def runtime_root(self) -> Path:
        return runtime.app_root(self.project_root, self.app_storage_dirname)

    @property
    def resource_root(self) -> Path:
        return runtime.resource_root(self.project_root)

    @property
    def executable_root(self) -> Path:
        return runtime.executable_root(self.project_root)

    @property
    def data_dir(self) -> Path:
        return self.runtime_root / "data"

    @property
    def db_path(self) -> Path:
        return self.data_dir / self.db_filename

    @property
    def vendor_dir(self) -> Path:
        return self.resource_root / "vendor"

    @property
    def vendored_deps_dir(self) -> Path:
        return self.resource_root / ".deps"

    @property
    def bundled_node_path(self) -> Path:
        return self.vendor_dir / "node" / "node.exe"

    @property
    def legacy_bundle_data_dir(self) -> Path:
        return self.executable_root / "data"

    @property
    def legacy_appdata_data_dir(self) -> Path:
        return runtime.local_appdata_root(self.app_storage_dirname) / "data"

    @property
    def starter_pack_path(self) -> Path:
        return self.resource_root / "resources" / "starter" / "dubindex_seed.db"

    @property
    def content_pool_path(self) -> Path:
        return self.resource_root / "resources" / "discovery" / "content_pool_v2.json"


def get_settings() -> Settings:
    return Settings(project_root=Path(__file__).resolve().parent.parent)
