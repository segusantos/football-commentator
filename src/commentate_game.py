from gfootball.env.config import Config
from gfootball.env.football_action_set import action_set_v1 as default_action_set

from football_commentator_env import FootballCommentatorEnv
from event_extractor import EventExtractor


def run_game(players: list) -> None:
    env = FootballCommentatorEnv(Config({
        "level": "11_vs_11_easy_stochastic",
        "action_set": "full",
        "players": players,
        "real_time": True,
        "physics_steps_per_frame": 5,
    }))
    event_extractor = EventExtractor()
    env.render()
    obs = env.reset()
    while True:
        obs, actions, done = env.step([])
        left_action = str(actions[0]) if actions[0] in default_action_set else "idle"
        right_action = str(actions[1]) if actions[1] in default_action_set else "idle"
        event_extractor.process_state(obs, left_action, right_action)
        if done:
            return


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--player1", default="bot:left_players=1")
    parser.add_argument("--player2", default="bot:right_players=1")
    args = parser.parse_args()
    player1 = args.player1
    player2 = args.player2
    print(f"Starting game with players: {player1} and {player2}")
    run_game([player1, player2])


if __name__ == "__main__":
    main()
