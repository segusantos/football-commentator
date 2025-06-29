from gfootball.env.config import Config
from gfootball.env.football_action_set import action_set_v1 as default_action_set

from football_commentator_env import FootballCommentatorEnv
from event_extractor import EventExtractor


def run_game(left_player: str, right_player: str) -> None:
    env = FootballCommentatorEnv(Config({
        "level": "11_vs_11_competition",
        "action_set": "full",
        "players": [
            f"{left_player}:left_players=1",
            f"{right_player}:right_players=1"
        ],
        "real_time": True,
    }))
    env.render()
    obs = env.reset()
    event_extractor = EventExtractor()
    while True:
        obs, actions, done = env.step([])
        left_action = str(actions[0]) if actions[0] in default_action_set else "idle"
        right_action = str(actions[1]) if actions[1] in default_action_set else "idle"
        event_extractor.process_state(obs, left_action, right_action)
        if done:
            obs = env.reset()


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--left_player", default="bot")
    parser.add_argument("--right_player", default="bot")
    args = parser.parse_args()
    left_player = args.left_player
    right_player = args.right_player
    print(f"Left player: {left_player}, Right player: {right_player}")
    run_game(left_player, right_player)


if __name__ == "__main__":
    main()
