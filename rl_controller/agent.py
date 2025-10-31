from __future__ import annotations

import random
from typing import Optional

from .action_space import Action, ActionSpace


class RandomAgent:
  """Baseline policy: uniformly random over the discrete action space."""

  def __init__(self, action_space: ActionSpace, seed: Optional[int] = None):
    self.action_space = action_space
    self._rng = random.Random(seed)

  def select_action(self, *_args, **_kwargs) -> Action:
    return self.action_space.random_action(self._rng)
