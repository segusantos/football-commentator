from gfootball.env.football_env import FootballEnv


class FootballCommentatorEnv(FootballEnv):
    def step(self, action):
        action = self._action_to_list(action)
        if self._agent:
            self._agent.set_action(action)
        else:
            assert len(
                action
            ) == 0, 'step() received {} actions, but no agent is playing.'.format(
                len(action))

        actions = self._get_actions()
        _, reward, done, info = self._env.step(actions)
        score_reward = reward
        if self._agent:
            reward = ([reward] * self._agent.num_controlled_left_players() +
                      [-reward] * self._agent.num_controlled_right_players())
        self._cached_observation = None
        info['score_reward'] = score_reward
        return self.observation(), actions, done
