"""Built-in rollout analyzers.

**Layout**

- ``generic/`` — default, task-agnostic analyzers (``artifact_manifest``, ``vlm_observer``, ``joints_csv_trajectory``).
  Do **not** add or modify these from the **robotics-devagent** skill; only product/harness
  changes.
- Task-specific rubric modules live under ``<validation_cfg_dir>/impl/<task>/<analyzer_type>.py`` in the
  repo (e.g. ``policies/impl/base_rotation/joints_csv_base_rotation.py``). Each module must define
  ``build(params: dict | None) -> RolloutAnalyzer``.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from typing import Any, Callable

from robot_manipulation_sim.validation.analyzers.base import RolloutAnalyzer
from robot_manipulation_sim.validation.analyzers.generic.artifact_manifest import ArtifactManifestAnalyzer
from robot_manipulation_sim.validation.analyzers.generic.joints_csv_trajectory import JointsCsvTrajectoryAnalyzer
from robot_manipulation_sim.validation.analyzers.generic.vlm_observer import VlmObserverAnalyzer

AnalyzerFactory = Callable[[dict[str, Any]], RolloutAnalyzer]

GENERIC_REGISTRY: dict[str, AnalyzerFactory] = {
    "artifact_manifest": lambda p: ArtifactManifestAnalyzer(p),
    "vlm_observer": lambda p: VlmObserverAnalyzer(p),
    "joints_csv_trajectory": lambda p: JointsCsvTrajectoryAnalyzer(p),
}


def _impl_analyzer_module_path(config_dir: Path, task_key: str, type_name: str) -> Path:
    return (config_dir / "impl" / task_key / f"{type_name}.py").resolve()


def _load_impl_factory(config_dir: Path, task_key: str, type_name: str) -> AnalyzerFactory | None:
    path = _impl_analyzer_module_path(config_dir, task_key, type_name)
    if not path.is_file():
        return None
    mod_name = f"_policy_impl_{task_key}_{type_name}"
    spec = importlib.util.spec_from_file_location(mod_name, path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    build_fn = getattr(module, "build", None)
    if not callable(build_fn):
        raise TypeError(
            f"task analyzer module {path} must define callable build(params: dict | None) -> analyzer "
            "(see robot_manipulation_sim.validation.analyzers docstring)"
        )

    def _factory(params: dict[str, Any] | None) -> RolloutAnalyzer:
        return build_fn(params or {})

    return _factory


def make_analyzer(
    analyzer_type: str,
    params: dict[str, Any] | None = None,
    *,
    task_key: str | None = None,
    config_dir: Path | None = None,
) -> RolloutAnalyzer:
    key = analyzer_type.strip()
    if key in GENERIC_REGISTRY:
        return GENERIC_REGISTRY[key](params or {})
    if task_key and config_dir:
        factory = _load_impl_factory(config_dir, task_key, key)
        if factory is not None:
            return factory(params or {})
    known = ", ".join(sorted(GENERIC_REGISTRY))
    hint = (
        f" For task mode, add {config_dir / 'impl' / (task_key or '<task>') / f'{key}.py'} with def build(params)."
        if config_dir
        else ""
    )
    raise KeyError(f"unknown analyzer type {analyzer_type!r}. Generic analyzers: {known}.{hint}")


__all__ = [
    "GENERIC_REGISTRY",
    "AnalyzerFactory",
    "RolloutAnalyzer",
    "make_analyzer",
]
