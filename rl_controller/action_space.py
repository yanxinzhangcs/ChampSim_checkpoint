from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence
import json
import random


@dataclass(frozen=True)
class ActionHead:
  """Single discrete knob in the action space."""

  name: str
  path: Sequence[str]
  choices: Sequence[str]

  def index_of(self, value: str) -> int:
    try:
      return self.choices.index(value)
    except ValueError as exc:  # pragma: no cover - defensive
      raise KeyError(f"Unknown choice '{value}' for head '{self.name}'") from exc


@dataclass(frozen=True)
class Action:
  """Concrete action assignment for all heads."""

  values: Mapping[str, str]

  def key(self) -> str:
    """Deterministic identifier for caching and logging."""
    return "_".join(f"{name}-{value}" for name, value in sorted(self.values.items()))

  def as_config_updates(self, heads: Mapping[str, ActionHead]) -> Dict[str, str]:
    """Convert the action to {path: value} modifications."""
    updates: Dict[str, str] = {}
    for name, value in self.values.items():
      head = heads.get(name)
      if head is None:
        raise KeyError(f"Unknown action head '{name}'")
      updates[".".join(head.path)] = value
    return updates

  def as_indices(self, heads: Mapping[str, ActionHead]) -> Dict[str, int]:
    """Return categorical indices for each head."""
    return {name: heads[name].index_of(value) for name, value in self.values.items()}


class ActionSpace:
  """Utility to manage multi-head discrete action selection."""

  def __init__(self, heads: Iterable[ActionHead]):
    self._heads: Dict[str, ActionHead] = {head.name: head for head in heads}

  @property
  def heads(self) -> Mapping[str, ActionHead]:
    return self._heads

  def choices(self) -> Mapping[str, Sequence[str]]:
    return {name: head.choices for name, head in self._heads.items()}

  def default_action(self) -> Action:
    return Action({name: head.choices[0] for name, head in self._heads.items()})

  def all_actions(self) -> List[Action]:
    names: List[str] = list(self._heads.keys())
    choice_lists: List[Sequence[str]] = [self._heads[name].choices for name in names]

    from itertools import product

    actions: List[Action] = []
    for combo in product(*choice_lists):
      actions.append(Action(dict(zip(names, combo))))
    return actions

  def random_action(self, rng: random.Random) -> Action:
    return Action({name: rng.choice(head.choices) for name, head in self._heads.items()})

  def from_dict(self, values: Mapping[str, str]) -> Action:
    # Validate values
    for name, value in values.items():
      head = self._heads.get(name)
      if head is None:
        raise KeyError(f"Unknown action head '{name}'")
      if value not in head.choices:
        raise ValueError(f"Invalid choice '{value}' for head '{name}' (choices={head.choices})")
    return Action(dict(values))


def load_action_space(config_path: Path) -> tuple[ActionSpace, Action, Path]:
  """Load action heads and base action from a JSON config file."""
  with config_path.open("r", encoding="utf-8") as handle:
    data = json.load(handle)

  heads = [
      ActionHead(name=head["name"], path=head["path"], choices=head["choices"]) for head in data["heads"]
  ]
  action_space = ActionSpace(heads)

  base_action_data: Dict[str, str] = data.get("base_action", {})
  if not base_action_data:
    base_action = action_space.default_action()
  else:
    base_action = action_space.from_dict(base_action_data)

  template_config = Path(data["template_config"]).resolve()
  return action_space, base_action, template_config
