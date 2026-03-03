from __future__ import annotations

import json
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import numpy as np

from .action_space import Action, ActionSpace

EPS = 1e-12
FEATURE_ORDER: Tuple[str, ...] = (
    "ipc",
    "l1d_mpki",
    "l2_mpki",
    "llc_mpki",
    "prefetch_coverage",
    "prefetch_accuracy",
    "branch_miss_rate",
)
DEFAULT_STATE_CUTOFFS: Tuple[float, ...] = (1.25, 0.02, 0.1, 0.1, 0.8, 0.7, 0.002)
NUM_STATE_BINS = 1 << len(DEFAULT_STATE_CUTOFFS)


class Agent:
  """Policy interface."""

  def select_action(self, state) -> Action:  # pragma: no cover - interface
    raise NotImplementedError

  def observe(self, state, action: Action, reward: float, next_state) -> None:  # pragma: no cover - interface
    raise NotImplementedError

  def finalize(self, final_state=None) -> None:
    """Optional hook after the final transition in an episode."""
    return


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


@dataclass
class _Transition:
  state: np.ndarray
  next_state: np.ndarray
  action_idx: int
  reward: float
  log_prob: float
  done: bool = False


class PPOAgent(Agent):
  """Discrete-action PPO agent with linear actor-critic models."""

  def __init__(
      self,
      action_space: ActionSpace,
      state_dim: int = 7,
      seed: Optional[int] = None,
      gamma: float = 0.99,
      gae_lambda: float = 0.95,
      clip_epsilon: float = 0.2,
      policy_lr: float = 0.01,
      value_lr: float = 0.02,
      value_coef: float = 0.5,
      entropy_coef: float = 0.0,
      rollout_size: int = 32,
      update_epochs: int = 4,
      minibatch_size: int = 32,
  ):
    self.action_space = action_space
    self.state_dim = state_dim
    self.gamma = gamma
    self.gae_lambda = gae_lambda
    self.clip_epsilon = clip_epsilon
    self.policy_lr = policy_lr
    self.value_lr = value_lr
    self.value_coef = value_coef
    self.entropy_coef = entropy_coef
    self.rollout_size = max(1, rollout_size)
    self.update_epochs = max(1, update_epochs)
    self.minibatch_size = max(1, minibatch_size)

    self._actions: Sequence[Action] = action_space.all_actions()
    if not self._actions:
      raise ValueError("Action space produced no actions")
    self._action_to_index: Dict[str, int] = {action.key(): idx for idx, action in enumerate(self._actions)}
    self._num_actions = len(self._actions)

    self._rng = np.random.default_rng(seed)
    init_scale = 0.05
    self._policy_w = self._rng.normal(0.0, init_scale, size=(self._num_actions, self.state_dim))
    self._policy_b = np.zeros(self._num_actions, dtype=np.float64)
    self._value_w = self._rng.normal(0.0, init_scale, size=(self.state_dim,))
    self._value_b = 0.0

    self._pending: Dict[str, object] | None = None
    self._buffer: List[_Transition] = []

  def select_action(self, state=None) -> Action:
    state_vec = self._state_to_array(state)
    probs = self._policy_probs(state_vec[None, :])[0]
    action_idx = int(self._rng.choice(self._num_actions, p=probs))
    log_prob = float(np.log(max(probs[action_idx], EPS)))
    self._pending = {"state": state_vec, "action_idx": action_idx, "log_prob": log_prob}
    return self._actions[action_idx]

  def observe(self, state, action: Action, reward: float, next_state) -> None:
    action_idx = self._action_to_index.get(action.key())
    if action_idx is None:
      raise KeyError(f"Unknown action '{action.key()}' for PPO agent")

    state_vec = self._state_to_array(state)
    log_prob = self._action_log_prob(state_vec, action_idx)
    if self._pending is not None and int(self._pending["action_idx"]) == action_idx:
      state_vec = self._pending["state"]  # type: ignore[assignment]
      log_prob = float(self._pending["log_prob"])
    self._pending = None

    next_state_vec = self._state_to_array(next_state)
    self._buffer.append(
        _Transition(
            state=state_vec,
            next_state=next_state_vec,
            action_idx=action_idx,
            reward=float(reward),
            log_prob=log_prob,
        )
    )

    if len(self._buffer) >= self.rollout_size:
      self._update_from_buffer()

  def finalize(self, final_state=None) -> None:
    if not self._buffer:
      return
    if final_state is not None:
      self._buffer[-1].next_state = self._state_to_array(final_state)
    self._buffer[-1].done = True
    self._update_from_buffer()

  def _state_to_array(self, state) -> np.ndarray:
    if state is None:
      return np.zeros(self.state_dim, dtype=np.float64)

    arr = np.asarray(state, dtype=np.float64).reshape(-1)
    if arr.size >= self.state_dim:
      return arr[: self.state_dim].copy()

    out = np.zeros(self.state_dim, dtype=np.float64)
    out[: arr.size] = arr
    return out

  def _policy_logits(self, states: np.ndarray) -> np.ndarray:
    return states @ self._policy_w.T + self._policy_b

  def _policy_probs(self, states: np.ndarray) -> np.ndarray:
    logits = self._policy_logits(states)
    logits = logits - np.max(logits, axis=1, keepdims=True)
    exp_logits = np.exp(logits)
    denom = np.clip(np.sum(exp_logits, axis=1, keepdims=True), EPS, None)
    return exp_logits / denom

  def _value(self, states: np.ndarray) -> np.ndarray:
    return states @ self._value_w + self._value_b

  def _action_log_prob(self, state_vec: np.ndarray, action_idx: int) -> float:
    probs = self._policy_probs(state_vec[None, :])[0]
    return float(np.log(max(probs[action_idx], EPS)))

  def _compute_advantages(
      self,
      rewards: np.ndarray,
      values: np.ndarray,
      next_values: np.ndarray,
      dones: np.ndarray,
  ) -> np.ndarray:
    advantages = np.zeros_like(rewards)
    gae = 0.0
    for idx in reversed(range(len(rewards))):
      mask = 1.0 - dones[idx]
      delta = rewards[idx] + self.gamma * next_values[idx] * mask - values[idx]
      gae = delta + self.gamma * self.gae_lambda * mask * gae
      advantages[idx] = gae
    return advantages

  def _update_from_buffer(self) -> None:
    if not self._buffer:
      return

    states = np.vstack([transition.state for transition in self._buffer])
    next_states = np.vstack([transition.next_state for transition in self._buffer])
    actions = np.asarray([transition.action_idx for transition in self._buffer], dtype=np.int64)
    rewards = np.asarray([transition.reward for transition in self._buffer], dtype=np.float64)
    old_log_probs = np.asarray([transition.log_prob for transition in self._buffer], dtype=np.float64)
    dones = np.asarray([1.0 if transition.done else 0.0 for transition in self._buffer], dtype=np.float64)

    values = self._value(states)
    next_values = self._value(next_states)
    advantages = self._compute_advantages(rewards, values, next_values, dones)
    returns = advantages + values

    adv_std = float(np.std(advantages))
    if adv_std > EPS:
      advantages = (advantages - np.mean(advantages)) / (adv_std + EPS)

    count = states.shape[0]
    batch_size = min(self.minibatch_size, count)
    indices = np.arange(count)
    for _ in range(self.update_epochs):
      self._rng.shuffle(indices)
      for start in range(0, count, batch_size):
        mb = indices[start : start + batch_size]
        self._update_minibatch(
            states=states[mb],
            actions=actions[mb],
            old_log_probs=old_log_probs[mb],
            advantages=advantages[mb],
            returns=returns[mb],
        )

    self._buffer.clear()

  def _update_minibatch(
      self,
      states: np.ndarray,
      actions: np.ndarray,
      old_log_probs: np.ndarray,
      advantages: np.ndarray,
      returns: np.ndarray,
  ) -> None:
    batch_size = states.shape[0]

    logits = self._policy_logits(states)
    probs = self._policy_probs(states)
    action_probs = np.clip(probs[np.arange(batch_size), actions], EPS, None)
    new_log_probs = np.log(action_probs)
    ratios = np.exp(new_log_probs - old_log_probs)

    lower = 1.0 - self.clip_epsilon
    upper = 1.0 + self.clip_epsilon
    unclipped_mask = ((advantages >= 0.0) & (ratios <= upper)) | ((advantages < 0.0) & (ratios >= lower))

    dloss_dlogp = np.zeros(batch_size, dtype=np.float64)
    dloss_dlogp[unclipped_mask] = -(advantages[unclipped_mask] * ratios[unclipped_mask]) / batch_size

    one_hot = np.zeros_like(logits)
    one_hot[np.arange(batch_size), actions] = 1.0
    grad_logits = dloss_dlogp[:, None] * (one_hot - probs)

    if self.entropy_coef != 0.0:
      log_probs = np.log(np.clip(probs, EPS, None))
      entropy = -np.sum(probs * log_probs, axis=1, keepdims=True)
      grad_entropy_loss = probs * (log_probs + entropy)
      grad_logits += (self.entropy_coef / batch_size) * grad_entropy_loss

    grad_policy_w = grad_logits.T @ states
    grad_policy_b = np.sum(grad_logits, axis=0)

    self._policy_w -= self.policy_lr * grad_policy_w
    self._policy_b -= self.policy_lr * grad_policy_b

    values = self._value(states)
    value_error = values - returns
    value_scale = self.value_coef * (2.0 / batch_size)
    grad_value_w = value_scale * np.sum(value_error[:, None] * states, axis=0)
    grad_value_b = value_scale * float(np.sum(value_error))

    self._value_w -= self.value_lr * grad_value_w
    self._value_b -= self.value_lr * grad_value_b


class HashTableAgent(Agent):
  """Contextual bandit backed by a 7-bit state hash table.

  The state vector is binned using per-feature cutoffs into one of 128 buckets
  (2^7). Each bucket stores per-action mean reward estimates and selects
  actions via epsilon-greedy over those estimates.
  """

  def __init__(
      self,
      action_space: ActionSpace,
      cutoffs: Sequence[float] = DEFAULT_STATE_CUTOFFS,
      epsilon: float = 0.1,
      seed: Optional[int] = None,
      table_path: Optional[Path] = None,
      initial_action: Optional[Action] = None,
  ):
    self.action_space = action_space
    self.cutoffs = tuple(float(x) for x in cutoffs)
    if len(self.cutoffs) != len(DEFAULT_STATE_CUTOFFS):
      raise ValueError(f"HashTableAgent requires {len(DEFAULT_STATE_CUTOFFS)} cutoffs (got {len(self.cutoffs)})")
    self.epsilon = float(epsilon)
    self._rng = random.Random(seed)

    self._actions: Sequence[Action] = action_space.all_actions()
    if not self._actions:
      raise ValueError("Action space produced no actions")
    self._action_by_key: Dict[str, Action] = {action.key(): action for action in self._actions}

    self.initial_action = initial_action or action_space.default_action()
    self.table_path = table_path

    # Bin -> action_key -> (value/count)
    self._values: Dict[int, Dict[str, float]] = {}
    self._counts: Dict[int, Dict[str, int]] = {}
    self._pending: Dict[str, object] | None = None

    if self.table_path is not None and self.table_path.exists():
      self._load_table(self.table_path)

  def select_action(self, state=None) -> Action:
    bin_id = self._bin_id(state)
    if self._rng.random() < self.epsilon:
      action = self.action_space.random_action(self._rng)
    else:
      action = self._best_action(bin_id)
    self._pending = {"bin_id": bin_id, "action_key": action.key()}
    return action

  def observe(self, state, action: Action, reward: float, next_state) -> None:
    action_key = action.key()
    if action_key not in self._action_by_key:
      raise KeyError(f"Unknown action '{action_key}' for HashTableAgent")

    bin_id = self._bin_id(state)
    if self._pending is not None and self._pending.get("action_key") == action_key:
      bin_id = int(self._pending.get("bin_id", bin_id))
    self._pending = None

    values = self._values.setdefault(bin_id, {})
    counts = self._counts.setdefault(bin_id, {})
    count = counts.get(action_key, 0) + 1
    counts[action_key] = count
    old_value = values.get(action_key, 0.0)
    values[action_key] = old_value + (float(reward) - old_value) / count

  def finalize(self, final_state=None) -> None:
    if self.table_path is None:
      return
    self._save_table(self.table_path)

  def _state_to_array(self, state) -> np.ndarray:
    if state is None:
      return np.zeros(len(self.cutoffs), dtype=np.float64)

    arr = np.asarray(state, dtype=np.float64).reshape(-1)
    if arr.size >= len(self.cutoffs):
      return arr[: len(self.cutoffs)].copy()

    out = np.zeros(len(self.cutoffs), dtype=np.float64)
    out[: arr.size] = arr
    return out

  def _bin_id(self, state) -> int:
    state_vec = self._state_to_array(state)
    bin_id = 0
    for idx, cutoff in enumerate(self.cutoffs):
      if float(state_vec[idx]) >= cutoff:
        bin_id |= 1 << idx
    return bin_id

  def _best_action(self, bin_id: int) -> Action:
    values = self._values.get(bin_id)
    if not values:
      return self.initial_action

    best_value = max(values.values())
    best_keys = [key for key, val in values.items() if val == best_value]
    chosen_key = self._rng.choice(best_keys)
    return self._action_by_key.get(chosen_key, self.initial_action)

  def _load_table(self, path: Path) -> None:
    with path.open("r", encoding="utf-8") as handle:
      data = json.load(handle)

    file_cutoffs = data.get("cutoffs")
    if file_cutoffs is not None:
      file_cutoffs_tuple = tuple(float(x) for x in file_cutoffs)
      if file_cutoffs_tuple != self.cutoffs:
        raise ValueError(f"Hash table cutoffs mismatch: file={file_cutoffs_tuple} agent={self.cutoffs}")

    policy = data.get("policy", {})
    for bin_key, action_key in policy.items():
      try:
        bin_id = int(bin_key)
      except (TypeError, ValueError):
        continue
      if action_key not in self._action_by_key:
        continue
      self._values.setdefault(bin_id, {})[action_key] = self._values.get(bin_id, {}).get(action_key, 0.0)
      self._counts.setdefault(bin_id, {})[action_key] = self._counts.get(bin_id, {}).get(action_key, 0)

    bins = data.get("bins", {})
    for bin_key, bin_data in bins.items():
      try:
        bin_id = int(bin_key)
      except (TypeError, ValueError):
        continue
      action_entries = {}
      if isinstance(bin_data, dict):
        action_entries = bin_data.get("actions", {}) or {}

      loaded_values: Dict[str, float] = {}
      loaded_counts: Dict[str, int] = {}
      for action_key, entry in action_entries.items():
        if action_key not in self._action_by_key or not isinstance(entry, dict):
          continue
        try:
          value = float(entry.get("value", 0.0))
          count = int(entry.get("count", 0))
        except (TypeError, ValueError):
          continue
        loaded_counts[action_key] = max(count, 0)
        loaded_values[action_key] = value

      if loaded_values:
        self._values.setdefault(bin_id, {}).update(loaded_values)
      if loaded_counts:
        self._counts.setdefault(bin_id, {}).update(loaded_counts)

  def _save_table(self, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    bins: Dict[str, Dict[str, object]] = {}
    policy: Dict[str, str] = {}
    for bin_id in range(NUM_STATE_BINS):
      values = self._values.get(bin_id, {})
      counts = self._counts.get(bin_id, {})
      if not values and not counts:
        continue
      actions: Dict[str, Dict[str, object]] = {}
      for action_key in set(values.keys()) | set(counts.keys()):
        actions[action_key] = {
            "value": float(values.get(action_key, 0.0)),
            "count": int(counts.get(action_key, 0)),
        }
      bins[str(bin_id)] = {"actions": actions}
      if values:
        best_key = max(values.items(), key=lambda item: item[1])[0]
        policy[str(bin_id)] = best_key

    data = {
        "version": 1,
        "feature_order": list(FEATURE_ORDER),
        "cutoffs": list(self.cutoffs),
        "epsilon": self.epsilon,
        "bins": bins,
        "policy": policy,
    }
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    with tmp_path.open("w", encoding="utf-8") as handle:
      json.dump(data, handle, indent=2, sort_keys=True)
    tmp_path.replace(path)
