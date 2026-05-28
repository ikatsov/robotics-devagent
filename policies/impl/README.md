# Task bundles (`impl/<task>/<task>.yaml` + `<task>.py` + analyzers)

Each **task name** is a single identifier (e.g. `base_rotation`) used consistently:

1. **`policies/validation.example.yaml`** (or your copy) — top-level **`task: <name>`** (must match the directory and filenames below).
2. **`policies/impl/<name>/<name>.yaml`** — `task_spec`, `task_analyzers`; rollout defaults live under **`artifacts/<name>/`** (relative to **`base_dir`** in the main validation YAML).
3. **`policies/impl/<name>/<name>.py`** — policy passed to **`simulate_policy.py`** (use **`--run-dir artifacts/<name>`** so validation’s default **`artifacts/<task>`** matches).
4. **`policies/impl/<name>/<analyzer_type>.py`** — optional task-specific analyzers; the YAML **`task_analyzers[].type`** must equal **`<analyzer_type>`** (the module stem). The module must define **`build(params) -> RolloutAnalyzer`**.

The harness requires the paired policy file **`policies/impl/<name>/<name>.py`** to exist whenever **`task:`** is set (see `load_validation_yaml` in `src/robot_manipulation_sim/validation/config.py`).

Paired unit tests live under **`tests/test_<name>.py`** (e.g. `tests/test_base_rotation.py`).
