from __future__ import annotations

import random
from dataclasses import dataclass
from typing import Dict, List, Optional, Sequence

import numpy as np

from .action_space import Action, ActionSpace

EPS = 1e-12


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
