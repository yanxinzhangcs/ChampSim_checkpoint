import unittest

from rl_controller.action_space import ActionHead, ActionSpace
from rl_controller.agent import SlidingUCBAgent


class SlidingUCBAgentTests(unittest.TestCase):
    def setUp(self):
        self.action_space = ActionSpace(
            [ActionHead(name="policy", path=["L1D", "prefetcher"], choices=["berti", "gaze"])]
        )
        self.berti, self.gaze = self.action_space.all_actions()

    def test_explores_each_action_before_scoring(self):
        agent = SlidingUCBAgent(self.action_space, c=0.0, window_size=3)

        self.assertEqual(agent.select_action(), self.berti)
        agent.observe(None, self.berti, 1.0, None)
        self.assertEqual(agent.select_action(), self.gaze)

    def test_uses_only_recent_rewards(self):
        agent = SlidingUCBAgent(self.action_space, c=0.0, window_size=2)
        for reward in (10.0, 0.0, 0.0):
            agent.observe(None, self.berti, reward, None)
        agent.observe(None, self.gaze, 1.0, None)

        self.assertEqual(agent.select_action(), self.gaze)

    def test_tracks_a_change_in_the_best_action(self):
        agent = SlidingUCBAgent(self.action_space, c=0.0, window_size=2)
        agent.observe(None, self.berti, 2.0, None)
        agent.observe(None, self.gaze, 1.0, None)
        self.assertEqual(agent.select_action(), self.berti)

        agent.observe(None, self.berti, 0.0, None)
        agent.observe(None, self.berti, 0.0, None)
        agent.observe(None, self.gaze, 3.0, None)
        self.assertEqual(agent.select_action(), self.gaze)


if __name__ == "__main__":
    unittest.main()
