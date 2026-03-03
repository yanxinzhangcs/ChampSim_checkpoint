import tempfile
import unittest
from pathlib import Path

from rl_controller.action_space import ActionHead, ActionSpace
from rl_controller.agent import HashTableAgent


class HashTableAgentTests(unittest.TestCase):
    def _make_action_space(self) -> ActionSpace:
        heads = [
            ActionHead(
                name="policy",
                path=["LLC", "replacement"],
                choices=["a", "b"],
            )
        ]
        return ActionSpace(heads)

    def test_bin_id_matches_cutoffs(self):
        action_space = self._make_action_space()
        agent = HashTableAgent(
            action_space=action_space,
            cutoffs=(1, 2, 3, 4, 5, 6, 7),
            epsilon=0.0,
            seed=0,
        )
        state = [1, 1, 4, 0, 6, 6, 7]
        self.assertEqual(agent._bin_id(state), 117)

    def test_selects_best_action_per_bin(self):
        action_space = self._make_action_space()
        base_action = action_space.default_action()
        action_a = base_action
        action_b = action_space.from_dict({"policy": "b"})

        agent = HashTableAgent(
            action_space=action_space,
            cutoffs=(0, 0, 0, 0, 0, 0, 0),
            epsilon=0.0,
            seed=0,
            initial_action=base_action,
        )
        state = [0.0] * 7

        self.assertEqual(agent.select_action(state).values["policy"], "a")
        agent.observe(state, action_a, 1.0, state)
        agent.observe(state, action_b, 2.0, state)
        self.assertEqual(agent.select_action(state).values["policy"], "b")

    def test_table_roundtrip(self):
        action_space = self._make_action_space()
        base_action = action_space.default_action()
        action_b = action_space.from_dict({"policy": "b"})
        state = [0.0] * 7

        with tempfile.TemporaryDirectory() as tmpdir:
            table_path = Path(tmpdir) / "hash_table.json"
            agent = HashTableAgent(
                action_space=action_space,
                cutoffs=(0, 0, 0, 0, 0, 0, 0),
                epsilon=0.0,
                seed=0,
                table_path=table_path,
                initial_action=base_action,
            )
            agent.observe(state, base_action, 1.0, state)
            agent.observe(state, action_b, 2.0, state)
            agent.finalize()

            agent2 = HashTableAgent(
                action_space=action_space,
                cutoffs=(0, 0, 0, 0, 0, 0, 0),
                epsilon=0.0,
                seed=123,
                table_path=table_path,
                initial_action=base_action,
            )
            self.assertEqual(agent2.select_action(state).values["policy"], "b")

