#!/usr/bin/env python3
from __future__ import annotations

import itertools
import json
import os
from pathlib import Path


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def dotted_path(path_list: list[str]) -> str:
    return ".".join(path_list)


def build_binary_name(action_updates: dict[str, str]) -> str:
    suffix = "_".join(f"{key.replace('.', '-')}-{value}" for key, value in sorted(action_updates.items()))
    return f"champsim_rl_{suffix}"


def print_combo_space(repo_root: Path, combo_path: Path, build_root: Path) -> None:
    combo_data = load_json(combo_path)
    heads = combo_data["heads"]
    template_path = (repo_root / combo_data["template_config"]).resolve()
    template = load_json(template_path)

    print(f"Combo action space: {combo_path}")
    print("Heads:")
    for head in heads:
        print(f"  - {head['name']}: path={dotted_path(head['path'])} choices={head['choices']}")

    names = [head["name"] for head in heads]
    choices = [head["choices"] for head in heads]
    combos = list(itertools.product(*choices))
    print(f"Total combos: {len(combos)}")
    for idx, combo in enumerate(combos, start=1):
        action = dict(zip(names, combo))
        print(f"  {idx:02d}) L1D={action.get('l1d_prefetcher')} L1I={action.get('l1i_prefetcher')} L2C={action.get('l2c_replacement')}")

    print(f"Template config: {template_path}")
    print(f"  L1I.replacement={template['L1I']['replacement']}")
    print(f"  L1D.replacement={template['L1D']['replacement']}")
    print(f"  L2C.prefetcher={template['L2C']['prefetcher']}")

    print("Build config checks:")
    for combo in combos:
        action = dict(zip(names, combo))
        updates = {dotted_path(head["path"]): action[head["name"]] for head in heads}
        name = build_binary_name(updates)
        config_path = build_root / f"{name}.json"
        if not config_path.exists():
            print(f"  {config_path}: MISSING")
            continue
        cfg = load_json(config_path)
        ok = (
            cfg["L1D"]["prefetcher"] == action["l1d_prefetcher"]
            and cfg["L1I"]["prefetcher"] == action["l1i_prefetcher"]
            and cfg["L2C"]["replacement"] == action["l2c_replacement"]
            and cfg["L1D"]["replacement"] == template["L1D"]["replacement"]
            and cfg["L1I"]["replacement"] == template["L1I"]["replacement"]
            and cfg["L2C"]["prefetcher"] == template["L2C"]["prefetcher"]
        )
        print(f"  {config_path}: {'OK' if ok else 'MISMATCH'}")


def print_baseline(repo_root: Path, baseline_path: Path) -> None:
    baseline_data = load_json(baseline_path)
    template_path = (repo_root / baseline_data["template_config"]).resolve()
    template = load_json(template_path)
    print(f"Baseline action space: {baseline_path}")
    print(f"Template config: {template_path}")
    expected = {
        "L1I": ("ip_stride", "lru"),
        "L1D": ("ip_stride", "lru"),
        "L2C": ("ip_stride", "lru"),
        "LLC": ("ip_stride", "lru"),
    }
    ok = True
    for level, (pref, repl) in expected.items():
        pref_ok = template[level]["prefetcher"] == pref
        repl_ok = template[level]["replacement"] == repl
        ok = ok and pref_ok and repl_ok
        print(f"  {level}.prefetcher={template[level]['prefetcher']} {level}.replacement={template[level]['replacement']}")
    print(f"Baseline template: {'OK' if ok else 'MISMATCH'}")


def print_summary_if_exists(repo_root: Path) -> None:
    summary_path = repo_root / "rl_results" / "perlbench_combo" / "experiment_summary.json"
    if not summary_path.exists():
        return
    summary = load_json(summary_path)
    fixed = summary.get("fixed_policies", {})
    best = summary.get("best_fixed_policy", {})
    print(f"Experiment summary: {summary_path}")
    print(f"  fixed_policies={len(fixed)} best={best.get('action', 'n/a')}")


def main() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    combo_path = repo_root / "rl_controller" / "action_space_perlbench_combo.json"
    baseline_path = repo_root / "rl_controller" / "action_space_perlbench_baseline.json"
    build_root = repo_root / "rl_controller" / "build_configs"

    print_combo_space(repo_root, combo_path, build_root)
    print_baseline(repo_root, baseline_path)
    print_summary_if_exists(repo_root)

    expected_ipv = "0 1 1 0 3#0 1 0 0 3"
    current_ipv = os.environ.get("L2C_IPV", "NOT SET")
    print(f"L2C_IPV: {current_ipv}")
    print(f"Expected: {expected_ipv}")


if __name__ == "__main__":
    main()
