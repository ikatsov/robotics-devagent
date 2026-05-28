---
name: robotics-devagent
description: >-
  Iterative MuJoCo UR5e + Robotiq policy development: user supplies a task name and a
  ``policies/impl/<task>/`` bundle (task YAML required); agent reads the spec, edits only
  policy/tests/custom analyzers and policy-side YAML, runs ``simulate_policy.py`` and
  ``validate_rollout.py``, then either deepens analysis (new or improved task-local analyzers:
  rules, VLM, vision models, etc.) or updates the policy after sufficient evidence—always
  presenting options and taking user direction until validation shows the task is solved.
  Policies must be built around robust robotics primitives (IK, vision, closed-loop state), not
  hand-tuned joint trajectories as the main strategy (see Policy design (strict) in the skill body).
  Follow structured development: explicit high-level module design first, incremental implementation
  with per-module validation, design revisions when evidence demands it, and task-local analyzers
  aligned to modules or phases where helpful.
  Must not modify the simulator or default validation harness (``src/``, ``scripts/``, MJCF), and must
  not change other tasks' policy/analyzer bundles—only read them as examples.
  Run simulate/validate only via shipped example configs (canonical CLI); no MUJOCO env overrides;
  do not invoke those scripts from pytest or headless agent shells.
  Use for manipulation tasks, rollout + VLM validation, and policy iteration in this repo.
---

# Robotics devagent — MuJoCo policy & validation loop

## Preconditions (agent must validate)

1. **Task name** — The user states the **exact** task stem **`<task>`** (e.g. `base_rotation`): letters, digits, `_`, `-`, `.` only; no path segments. If missing or ambiguous, **ask** before editing.

2. **Task bundle directory** — The user must have created **`policies/impl/<task>/`** at the **repository root** (i.e. `policies/impl/{name}/` next to `policies/validation.example.yaml`; not under `src/`).

3. **Task specification YAML** — The file **`policies/impl/<task>/<task>.yaml`** **must exist** before the skill proceeds. It holds **`task_spec`** (e.g. **`inline`** intent), **`task_analyzers`**, and optional **`policy_module`**. If the folder or **`{task}.yaml`** is missing, **stop**: tell the user to create the directory and the spec file, then re-invoke the skill.

4. **Policy module** — For validation with **`task:`** set, the harness requires **`policies/impl/<task>/<task>.py`** to exist (the agent may create or rewrite it after reading the spec). Do not rename the stem away from **`<task>`**.

## Hard boundary (do not violate)

**Do not modify** the simulator or the **default validation harness**, including:

- **`scripts/**`**, **`src/robot_manipulation_sim/**`** (env, MJCF, **`validation/analyzers/generic/`**, **`make_analyzer`** loader, etc.)
- **`pyproject.toml`**, unrelated **`tests/**`**, **`.cursor/**`**, **`README.md`**, CI, or vendored assets

**Shared example configs (read-only templates)** — **`policies/simulate_policy.example.yaml`** and **`policies/validation.example.yaml`**:

- **Do not copy** them to per-task files (e.g. **`policies/simulate_<task>.yaml`**, **`policies/validation_<task>.yaml`**) or fork their contents into new YAML under **`policies/`**.
- **Do not edit** them except **`task:`** in **`policies/validation.example.yaml`** (set to **`<task>`** before **`validate_rollout.py`**). Leave every other key (analyzers, VLM params, **`rgb`**, video grid, …) as shipped.
- For **`simulate_policy.py`**, **prefer CLI overrides** so **`simulate_policy.example.yaml`** stays unchanged: pass **`policies/impl/<task>/<task>.py`** and **`--run-dir artifacts/<task>`** only (see **Simulation and validation execution (strict)**). **`rgb: true`** and other harness defaults already live in the example YAML—do not duplicate them with extra CLI flags unless the user explicitly changes the shipped example. Only if the user insists on YAML-only invocation, change **only** **`policy_file`** and **`run_dir`** in the example file to match **`<task>`**—still no other edits.

**You may edit only** files under the **current** task stem **`<task>`** (never another folder under `policies/impl/`):

- **`policies/impl/<task>/<task>.py`** — policy implementation (`policy(obs, step, env)`, helpers, optional `reset`); must follow **Policy design (strict)** below
- **`policies/impl/<task>/<task>.yaml`** — task specification, **`task_analyzers`** list, thresholds in **`params`**
- **`policies/impl/<task>/<analyzer_type>.py`** — **custom task analyzers** (filename stem = YAML **`type`**; must export **`build(params) -> RolloutAnalyzer`**; may call VLM APIs, OpenCV, YOLO-World, joint-log math, etc.—keep dependencies and secrets out of committed files unless the user agrees)
- **Not** **`policies/simulate_policy.example.yaml`** or **`policies/validation.example.yaml`** (see **Shared example configs** above). Do not change shipped **Python** harness code.
- **`tests/test_<task>.py`** — the **single** paired unit test for this stem (create only with user OK if it does not exist). **Headless only**—must **not** subprocess or import-run **`simulate_policy.py`** / **`validate_rollout.py`** (see **Simulation and validation execution (strict)**).

You may **read** harness and [reference.md](reference.md) for API names, artifact layout, and VLM env vars.

### Other task bundles (read-only examples)

- **Do not modify** any **other** task’s implementation: **`policies/impl/<other>/<other>.py`**, **`policies/impl/<other>/<analyzer_type>.py`**, **`policies/impl/<other>/<other>.yaml`**, or **`tests/test_<other>.py`** whenever **`<other> ≠ <task>`** (even for a “quick fix” or copy-paste cleanup).
- **Do read** those files **as examples**: control patterns (phasing, gripper handling, joint indexing), how **`build(params)`** analyzers are structured, YAML **`task_analyzers`** / **`params`** conventions, and test style—then apply the idea **only** inside **`policies/impl/<task>/`** and **`tests/test_<task>.py`**.

## Policy design (strict)

**The central approach must not be** long sequences of **hand-picked joint-space keyframes** (or equivalent fixed ``ctrl`` playlists) chosen mainly by trial-and-error to match one scene layout. That pattern is brittle: it ignores gravity/tracking error, configuration multiplicity, and small scene or noise changes.

**Prefer robust robotics programming** as the backbone of **`policies/impl/<task>/<task>.py`**, for example:

- **Inverse kinematics** — numerical or analytic IK toward **task-relevant frames** (e.g. grasp/place poses derived from ``obs`` / MuJoCo body or site positions, not magic constants alone). Use the bundled env/model from ``obs`` / ``env`` (e.g. Jacobian-based damped least squares with ``mujoco.mj_jac``, constrained optimization on ``qpos``, external IK libraries, or iterative site-target refinement) **inside the policy module** so behavior tracks the actual state.
- **Computer vision / perception** — Treat camera frames in **`obs["images"]`** (e.g. scene and wrist tiles from the bundled MJCF) as **always available** for the real task: use them for alignment, segmentation, or error signals as the **primary** perception path.
- **Control structure** — impedance- or velocity-like stepping toward IK solutions, integrators on error, phase machines that **branch on state** (contact, height thresholds, grasp width), not only on ``step``.

**Allowed:** a modest number of **hardcoded scalars** (gains, timeouts, nominal offsets, safety clamps, default seeds) and **short** anchor postures (e.g. a named ``HOME``) **when they support** the algorithmic core, not when they *replace* it.

**Escalation:** If IK/vision is blocked only because the harness denies needed APIs or dependencies, say so clearly and propose the smallest **task-local** workaround—or ask the user to extend the harness outside this skill.

## Structured policy development (required)

Do **not** grow the policy as one undifferentiated blob. Use a **documented, modular plan** and **incremental** integration so each piece can be exercised and diagnosed cleanly.

### A — High-level design (before or alongside first serious code)

After reading **`task_spec`** and the spec YAML, produce an explicit **policy architecture** (in the agent’s reply to the user at minimum; a short structured summary is enough). It should name the **modules** you intend, what each is responsible for, and how data flows between them—for example:

- **Perception** — which cameras or state channels, what outputs (e.g. table ``(x,y)``, features, phase triggers).
- **Planning / setpoints** — nominal poses, locks, splines, or contact-relative targets.
- **IK / tracking** — how setpoints become joint or Cartesian commands (damping, caps, orientation objectives).
- **Phases / logic** — state machines or step bands; what transitions them (distance, time, vision, contact).
- **Gripper / contact** — when and how to open, close, release; any latch rules.
- **Safety / limits** — clamps, timeouts, fallbacks.

Keep this design **aligned** with **Policy design (strict)** (IK + vision backbone, not a joint playlist as the main idea).

### B — Step-by-step implementation and validation

**Prefer** to land the policy in **ordered steps**, each small enough to simulate and validate in isolation:

1. Implement or wire **one module** (or one phase) at a time; keep other stages **inert or trivially correct** (e.g. fixed safe setpoint, no-op grasp) until the active module is verified.
2. After each meaningful step, run **pytest** (paired tests, headless only), then have **simulation + validation** run via the **canonical commands** in **Simulation and validation execution (strict)**—not from pytest and not with custom MuJoCo env vars.
3. Only then compose the next module or tighten coupling between blocks.

Goal: when something fails, **artifacts** point to a **narrow** subsystem (vision ray error vs IK vs phase vs gripper), not the whole file.

### C — Revisit the design every iteration

After each simulation/validation round, **compare results to the current architecture**:

- If tuning alone is insufficient, or failures implicate the wrong split of responsibilities, **revise the high-level design**: add/remove modules, change interfaces (e.g. perception feeds IK targets vs separate servo), or replace an approach (e.g. more state-based gating vs time-only phases).
- Present the **updated architecture** to the user when it changes, with **evidence** (metrics, analyzer JSON, short log excerpts) for why the previous split was inefficient or wrong.

### D — Analyzers matched to modules and phases

**Prefer** **task-local analyzers** (**`policies/impl/<task>/<type>.py`**) that validate **one concern** or **one episode segment** well—for example: early exploration kinematics, vision-proxy metrics on **`joints.csv`** or artifacts, hover-height band before grasp, lift height, place stability, smoothness in a time window. Register them in **`task_analyzers`** with **`params`** tuned to that module or phase.

Use **generic** harness analyzers for broad checks; add **specialized** ones when a module needs a clear pass/fail or diagnostic signal that generic tools do not express.

## Simulation and validation execution (strict)

Rollout generation and rollout validation are **harness scripts** with **fixed, shipped configuration**. Treat them differently from **pytest**.

### Canonical commands (only these shapes)

From the **repository root**, with the project venv active (e.g. **`pip install -e ".[vlm]"`** when VLM analyzers are used):

```bash
pytest -q tests/test_<task>.py

python scripts/simulate_policy.py --config policies/simulate_policy.example.yaml \
  policies/impl/<task>/<task>.py --run-dir artifacts/<task>

# Edit only ``task: <task>`` in policies/validation.example.yaml, then:
python scripts/validate_rollout.py --config policies/validation.example.yaml
```

**Allowed overrides for simulate:** **`--config policies/simulate_policy.example.yaml`**, the **policy path** positional argument, and **`--run-dir artifacts/<task>`** so outputs land under **`artifacts/<task>/`**. Everything else (**`steps`**, **`rgb`**, video grid, joint log interval, …) comes from **`simulate_policy.example.yaml`** as shipped.

**Allowed overrides for validate:** **`--config policies/validation.example.yaml`** only, plus setting **`task: <task>`** in that file (no other keys).

### Forbidden for simulate / validate

- **Do not** set or export **`MUJOCO_GL`**, **`MUJOCO_EGL`**, or any other MuJoCo / rendering environment override “to make sim work” in the agent shell, CI, or docs—the harness is expected to run with **default** MuJoCo GL behavior on the user’s machine.
- **Do not** pass non-standard CLI flags to **`simulate_policy.py`** or **`validate_rollout.py`** (extra **`--rgb`**, custom **`--config`** copies, alternate YAML paths, **`MUJOCO_*` wrappers**, etc.) unless the **user explicitly** requests a change to the shipped example configs or flags.
- **Do not** fork **`policies/simulate_<task>.yaml`** / **`policies/validation_<task>.yaml`** (see **Shared example configs**).
- **Do not** invoke **`simulate_policy.py`** or **`validate_rollout.py`** from **`tests/`** (no subprocess, no importing the script module to run a full rollout inside pytest). Unit tests stay **headless** (**`UR5GripperEnv(enable_rgb=False)`**, small fixtures, analyzer logic on sample **`joints.csv`** rows).

### Who runs sim / validate

- **Default:** Ask the **user** to run the two canonical commands in their own terminal (where rendering already works). The agent reviews **`artifacts/<task>/`** afterward.
- **Agent may run** simulate/validate only when the user explicitly wants that in an environment known to support MuJoCo rendering—still **only** the canonical commands above, **no** MuJoCo env overrides.
- **Do not** run **`simulate_policy.py --rgb`** (or full RGB rollouts) from agent/sandbox/CI shells that lack a working display/GL context; that produces misleading simulator errors unrelated to the policy.

## Workflow (mandatory order)

### 1 — Validate inputs

Confirm **`<task>`** and that **`policies/impl/<task>/<task>.yaml`** exists (and optionally **`{task}.py`**). Abort with clear instructions if not.

### 2 — Read spec, **document architecture**, then implement

Load **`policies/impl/<task>/<task>.yaml`**. Summarize goals, constraints, success signals, and what the sim can observe.

**Before** writing a full monolithic policy, follow **Structured policy development (required)**: produce the **high-level module design** (§A), then implement **incrementally** (§B), adding or adjusting **task-local analyzers** as you go (§D).

**Implement or modify** **`policies/impl/<task>/<task>.py`** so structure in code **reflects** the named modules (clear helpers or sections, stable data flow between perception → setpoints → IK → phases → gripper). Adjust **`tests/test_<task>.py`** when behavior contracts change.

### 3 — Run simulation and validation

Follow **Simulation and validation execution (strict)**: **pytest** first (headless); then simulate + validate via the **canonical commands** only—standard configs, no MuJoCo env flags, not from tests.

Consume **`artifacts/<task>/`**: **`rollout.mp4`**, **`metrics.txt`**, **`joints.csv`**, analyzer JSON (**`rollout.*.json`**), **`rollout.vlm.json`** if enabled. Details: [reference.md](reference.md).

### 3b — Revisit architecture

Apply **Structured policy development §C**: if evidence shows the current module split or interfaces are wrong, **update the design first** (what modules exist and how they combine), then change code and analyzers to match.

### 4 — Analyze outputs; choose next move

After **sufficient** review of artifacts vs **`task_spec`** and vs the **current high-level design**, pick **one** primary direction (you may combine lightly, but stay clear):

- **4.0 — Architecture / module plan** — When validation shows a **structural** misfit (wrong responsibilities, missing phase, perception not feeding the right law), revise the **design** (§A, §C) before deep tuning of the old shape.

- **4.1 — Deeper analysis** — Add or **refine custom analyzers** under **`policies/impl/<task>/`** (new **`<analyzer_type>.py`** + **`task_analyzers`** entry, or improve existing modules). Prefer **module- or phase-specific** checks (**§D**): rubrics tied to the task text, time windows, **`joints.csv`** metrics, VLM prompts scoped to one stage, etc. Re-run **`validate_rollout.py`** (and sim only if new signals need fresh logs).

- **4.2 — Policy update** — **Only** when analysis shows **what** to change inside the agreed modules (IK targets, Jacobians/gains, perception hooks, timing, phase logic on state, missing reset). Edit **`policies/impl/<task>/<task>.py`** (and tests) while respecting **Policy design (strict)** and the **documented architecture**, then re-run **pytest → simulate → validate**.

Do **not** jump to large policy rewrites on a vague VLM narrative; ground decisions in **metrics, JSON verdicts, and logs**.

### 5 — User in the loop

**Present** the situation: evidence summary, what passed/failed, whether the **architecture** still fits, and **explicit options** (e.g. “revise design: merge perception + approach” vs “extend analyzer X for hover phase” vs “change IK target in module …”). **Wait for user feedback** on which branch (**4.0** / **4.1** / **4.2**) and any constraints. Proceed accordingly.

### 6 — Stopping condition

Continue iterations until **validation outputs** (including task-specific **`pass`** / exit codes and alignment with **`task_spec`**) support a defensible **“task solved”** conclusion. If the blocker is harness, scene, or generic analyzer code, **stop** and ask the user to change those outside this skill.

## Custom analyzers (reminders)

- One module per **`task_analyzers[].type`**: **`policies/impl/<task>/<type>.py`** with **`build(params)`**.
- Prefer **small**, testable modules; put tunables in YAML **`params`**, not magic numbers in code when avoidable.
- **Align analyzers to the policy architecture** (**Structured policy development §D**): when the policy has distinct phases or subsystems (explore, approach, grasp, lift, place), consider **one focused analyzer per concern** or **per time band** so pass/fail and metrics map cleanly to the module under iteration—rather than one oversized rubric that is hard to interpret when only one stage regresses.
- Reuse **generic** harness analyzers (**`vlm_observer`**, **`joints_csv_trajectory`**, **`artifact_manifest`**) via the main validation YAML only by **configuration**—do not copy their implementations into `src/`.

## Quick checklist

- [ ] **`<task>`** from user; **`policies/impl/<task>/<task>.yaml`** exists
- [ ] **High-level policy architecture** written (modules, roles, data flow) per **Structured policy development §A**
- [ ] Read spec → incremental policy + analyzers per **§B** / **§D**; code structure matches the named modules
- [ ] After each validation round, **§C** — revise architecture if evidence demands it
- [ ] `pytest` (headless only) → canonical `simulate_policy.py` + `validate_rollout.py` (standard configs; **no** `MUJOCO_*` env; **not** from tests)
- [ ] Analyze artifacts; choose **4.0** / **4.1** / **4.2** with justification
- [ ] Respect **read-only other tasks**; only edit **`policies/impl/<task>/`** + **`tests/test_<task>.py`**
- [ ] Do **not** copy or retune **`simulate_policy.example.yaml`** / **`validation.example.yaml`** (validation: **`task:`** only; sim: CLI overrides)
- [ ] **Describe options to the user**; incorporate feedback; repeat until solved or escalated
