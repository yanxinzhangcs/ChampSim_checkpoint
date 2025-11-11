from __future__ import annotations

import random
from typing import Optional, Sequence

from .action_space import Action, ActionSpace


class Agent:
  """Policy interface."""

  def select_action(self, state) -> Action:  # pragma: no cover - interface
    raise NotImplementedError

  def observe(self, state, action: Action, reward: float, next_state) -> None:  # pragma: no cover - interface
    raise NotImplementedError


class RandomAgent(Agent):
  """Baseline policy: uniformly random over the discrete action space."""

  def __init__(self, action_space: ActionSpace, seed: Optional[int] = None):
    self.action_space = action_space
    self._rng = random.Random(seed)

  def select_action(self, state=None) -> Action:
    return self.action_space.random_action(self._rng)

  def observe(self, state, action: Action, reward: float, next_state) -> None:
    # Pure exploration; no learning
    return


class EpsilonGreedyAgent(Agent):
  """Tabular epsilon-greedy bandit over the discrete action combinations."""

  def __init__(self, action_space: ActionSpace, epsilon: float = 0.1, seed: Optional[int] = None):
    self.action_space = action_space
    self._rng = random.Random(seed)
    self.epsilon = epsilon
    self._actions: Sequence[Action] = action_space.all_actions()
    if not self._actions:
      raise ValueError("Action space produced no actions")
    self._values = {action.key(): 0.0 for action in self._actions}
    self._counts = {action.key(): 0 for action in self._actions}

  def select_action(self, state=None) -> Action:
    if self._rng.random() < self.epsilon:
      return self.action_space.random_action(self._rng)

    # Exploit: pick action with highest estimated value
    best_value = None
    best_actions = []
    for action in self._actions:
      value = self._values[action.key()]
      if best_value is None or value > best_value:
        best_value = value
        best_actions = [action]
      elif value == best_value:
        best_actions.append(action)

    return self._rng.choice(best_actions)

  def observe(self, state, action: Action, reward: float, next_state) -> None:
    key = action.key()
    count = self._counts[key] + 1
    self._counts[key] = count
    value = self._values[key]
    # Incremental mean
    self._values[key] = value + (reward - value) / count
