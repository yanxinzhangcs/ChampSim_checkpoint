## Control Target

The action is a combination of ChampSim hardware policies, such as:

```text
L1D prefetcher
L1I prefetcher
L2C replacement policy
```

In the main combo setup, the action space is:

```text
L1D prefetcher: berti / gaze
L1I prefetcher: entangling / barca
L2C replacement: mockingjay / PACIPV
```

This gives 8 possible actions.

## RL Loop

The episode starts from a warmed-up cache checkpoint. Then, for each simulation window:

```text
1. The agent observes the previous window state.
2. The agent selects one policy combination.
3. ChampSim runs the next window using that policy.
4. ChampSim produces JSON statistics.
5. The statistics are parsed into the next state.
6. The window IPC is used as the reward.
7. The cache checkpoint is saved for the next window.
```

## State

The state is a 7-dimensional vector extracted from ChampSim statistics:

```text
ipc
l1d_mpki
l2_mpki
llc_mpki
prefetch_coverage
prefetch_accuracy
branch_miss_rate
```

The first step starts with an empty state, represented as zeros by the PPO agent.

## Reward

The reward is the IPC of the current simulation window:

```text
reward = window IPC
```

## Agents

The project includes several agents:

```text
random
epsilon_greedy
hash_table
ppo
```

The main experiments use a lightweight NumPy PPO implementation with a linear actor-critic model over the discrete action space.

## Checkpointing

Cache checkpointing is used to connect consecutive windows. ChampSim saves cache contents after each window and reloads them before the next one. This allows the RL rollout to approximate a continuous execution across multiple policy choices.

Relevant implementation files:

```text
src/main.cc
src/champsim.cc
src/cache_checkpoint.cc
src/cache.cc
```

## Evaluation Data

The experiment summary records:

```text
RL-selected actions and rewards
fixed-policy baseline results
best fixed policy
per-step best action comparison
```

This data is used to compare the RL policy against fixed policies and per-window best-action choices.
