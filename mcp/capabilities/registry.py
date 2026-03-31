from __future__ import annotations

from pathlib import Path
from typing import Dict

from capability_introspection import capability_map
from capabilities.base import CapabilityModule
from capabilities.fs_module import FilesystemCapabilityModule
from capabilities.ingest_artifact_module import IngestArtifactCapabilityModule
from capabilities.ingest_tool_event_module import IngestToolEventCapabilityModule
from capabilities.noop_module import NoopEchoCapabilityModule
from capabilities.tool_catalog_module import ToolCatalogCapabilityModule

_FS_CAPS = ("FS_MOVE", "FS_COPY", "FS_DELETE_EXEC", "FS_DELETE_NONEXEC")


class CapabilityRegistry:
    def __init__(self, modules: Dict[str, CapabilityModule]) -> None:
        self._modules = dict(sorted(modules.items(), key=lambda kv: kv[0]))

    def names(self) -> list[str]:
        return sorted(self._modules.keys())

    def get(self, name: str) -> CapabilityModule | None:
        return self._modules.get(name)



def build_registry(registry_path: Path) -> CapabilityRegistry:
    cmap = capability_map(registry_path)
    modules: Dict[str, CapabilityModule] = {}
    for name in _FS_CAPS:
        tool = cmap.get(name, {})
        args_spec = tool.get("args", {}) if isinstance(tool, dict) else {}
        modules[name] = FilesystemCapabilityModule(name, args_spec)
    modules["INGEST_ARTIFACT"] = IngestArtifactCapabilityModule()
    modules["INGEST_TOOL_EVENT"] = IngestToolEventCapabilityModule()
    modules["NOOP_ECHO"] = NoopEchoCapabilityModule()
    modules["TOOL_REGISTER"] = ToolCatalogCapabilityModule()
    return CapabilityRegistry(modules)
