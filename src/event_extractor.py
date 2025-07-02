from enum import Enum
import json
from time import perf_counter
import numpy as np


FIELD_HALF_LENGTH = 1.0
FIELD_HALF_WIDTH = 0.42
GOAL_HALF_WIDTH = 0.044


class GameMode(Enum):
    NORMAL = 0
    KICKOFF = 1
    GOALKICK = 2
    FREEKICK = 3
    CORNER = 4
    THROWIN = 5
    PENALTY = 6


class EventExtractor:
    def __init__(self):
        # Load data
        self.metadata = json.load(open("/gfootball/metadata.json", "r"))

        # Match state
        self.total_steps = None
        self.match_time = 0.0
        self.event_cnt = 0
        self.last_event_time = perf_counter()
        self.goal_events = []
        self.card_events = []

        # Events metadata
        self.prev_obs = None
        self.prev_owned_state = None
        self.pass_state = None
        self.shot_state = None

        self.publish_event({
            "type": "start_of_match",
            "match_metadata": self.metadata
        })

    def set_match_time(self, steps_left: int) -> str:
        self.match_time = 90 * 60 * (self.total_steps - steps_left) / self.total_steps

    def get_location_description(self, location: np.ndarray) -> str:
        x = (location[0] + FIELD_HALF_LENGTH) / (2 * FIELD_HALF_LENGTH)
        y = (location[1] + FIELD_HALF_WIDTH) / (2 * FIELD_HALF_WIDTH)
        if x < 3**-1:
            x_description = "left"
        elif 3**-1 <= x < 2 * 3**-1:
            x_description = "center"
        else:
            x_description = "right"
        if y < 3**-1:
            y_description = "top"
        elif 3**-1 <= y < 2 * 3**-1:
            y_description = "middle"
        else:
            y_description = "bottom"
        return f"{x_description}_{y_description}"

    def is_directional(self, action: str) -> bool:
        return action in set([
            "action_left",
            "action_top_left",
            "action_top",
            "action_top_right",
            "action_right",
            "action_bottom_right",
            "action_bottom",
            "action_bottom_left"
        ])
    
    def is_pass(self, action: str) -> bool:
        return action in set([
            "short_pass",
            "long_pass",
            "high_pass"
        ])
    
    def is_kick(self, action: str) -> bool:
        return action == "shot" or self.is_pass(action)
    
    def publish_event(self, event_data: dict) -> None:
        self.event_cnt += 1
        event = {
            "event_id": self.event_cnt,
            "match_time": f"{self.match_time//60:02.0f}:{self.match_time % 60:02.0f}",
        }
        event.update(event_data)
        print(json.dumps(event, indent=4))
        print(int(perf_counter() - self.last_event_time), "seconds since last event")
        self.last_event_time = perf_counter()

    def process_state(self, obs: dict, left_action: str, right_action: str) -> None:
        if obs["steps_left"] == 0:
            self.publish_event({
                "type": "end_of_match",
                "team_left": self.metadata["left_team"]["name"],
                "score_left": obs["score"][0],
                "team_right": self.metadata["right_team"]["name"],
                "score_right": obs["score"][1],
                "goal_events": self.goal_events,
                "card_events": self.card_events
            })
            return
        if self.total_steps is None:
            self.total_steps = obs["steps_left"]
        self.set_match_time(obs["steps_left"])

        # Capture events based on observations
        if self.prev_obs is not None and self.prev_obs["score"] != obs["score"]:
            if obs["score"][0] > self.prev_obs["score"][0]:
                scoring_team = self.metadata["left_team"]
            else:
                scoring_team = self.metadata["right_team"]
            goal_event = {
                "type": "goal",
                "subtype": "own_goal" if self.shot_state is not None and self.shot_state["team"] != scoring_team["name"] else "goal",
                "scorer": self.shot_state["player"] if self.shot_state is not None else None,
                "location": self.shot_state["location"] if self.shot_state is not None else None,
                "scoring_team": scoring_team["name"],
                "team_left": self.metadata["left_team"]["name"],
                "score_left": obs["score"][0],
                "team_right": self.metadata["right_team"]["name"],
                "score_right": obs["score"][1],
            }
            self.goal_events.append(goal_event)
            self.publish_event(goal_event)
            self.shot_state = None
        if self.prev_obs is not None and not np.array_equal(obs["left_team_yellow_card"], self.prev_obs["left_team_yellow_card"]):
            for i, (prev_card, curr_card) in enumerate(zip(self.prev_obs["left_team_yellow_card"], obs["left_team_yellow_card"])):
                if curr_card and not prev_card:
                    player = self.metadata["left_team"]["players"][i]
                    card_event = {
                        "type": "yellow_card",
                        "player": player,
                        "team": self.metadata["left_team"]["name"],
                    }
                    self.card_events.append(card_event)
                    self.publish_event(card_event)
        if self.prev_obs is not None and not np.array_equal(obs["right_team_yellow_card"], self.prev_obs["right_team_yellow_card"]):
            for i, (prev_card, curr_card) in enumerate(zip(self.prev_obs["right_team_yellow_card"], obs["right_team_yellow_card"])):
                if curr_card and not prev_card:
                    player = self.metadata["right_team"]["players"][i]
                    card_event = {
                        "type": "yellow_card",
                        "player": player,
                        "team": self.metadata["right_team"]["name"],
                    }
                    self.card_events.append(card_event)
                    self.publish_event(card_event)
        if self.prev_obs is not None and not np.array_equal(obs["left_team_active"], self.prev_obs["left_team_active"]):
            for i, (prev_active, curr_active) in enumerate(zip(self.prev_obs["left_team_active"], obs["left_team_active"])):
                if not curr_active and prev_active:
                    player = self.metadata["left_team"]["players"][i]
                    card_event = {
                        "type": "red_card",
                        "player": player,
                        "team": self.metadata["left_team"]["name"],
                    }
                    self.card_events.append(card_event)
                    self.publish_event(card_event)
        if self.prev_obs is not None and obs["game_mode"] not in [GameMode.NORMAL, GameMode.KICKOFF] and obs["game_mode"] != self.prev_obs["game_mode"]:
            game_mode_event = {
                "type": "game_mode_change",
                "previous_mode": self.prev_obs["game_mode"],
                "current_mode": obs["game_mode"],
            }
            self.publish_event(game_mode_event)

        # Capture events based on actions
        if obs["ball_owned_team"] == -1:
            self.prev_obs = obs
            return            

        # Init variables
        if obs["ball_owned_team"] == 0:
            attacking_team = self.metadata["left_team"]
            attacking_obs = obs["left_team"]
            attacking_action = left_action
        else:
            attacking_team = self.metadata["right_team"]
            attacking_obs = obs["right_team"]
            attacking_action = right_action
        attacking_player = attacking_team["players"][obs["ball_owned_player"]]
        attacking_player_location = self.get_location_description(attacking_obs[obs["ball_owned_player"]])

        # Capture the second action of two-step events
        if self.pass_state is not None and self.pass_state["player"] != attacking_player:
            self.publish_event({
                "type": self.pass_state["type"],
                "subtype": self.pass_state["subtype"],
                "seconds_interval": int(self.match_time - self.pass_state["match_time"]),
                "team": self.pass_state["team"],
                "passer": self.pass_state["player"],
                "location_pass": self.pass_state["location"],
                "receiver": attacking_player,
                "location_reception": attacking_player_location,
                "pass_completed": self.pass_state["team"] == attacking_team["name"],
            })
            self.pass_state = None
        elif self.prev_owned_state is not None and self.prev_owned_state["player"] != attacking_player:
            self.publish_event({
                "type": "ball_possession_change",
                "subtype": "same_team" if self.prev_owned_state["team"] == attacking_team["name"] else "different_team",
                "current_team": attacking_team["name"],
                "previous_team": self.prev_owned_state["team"],
                "current_player": attacking_player,
                "previous_player": self.prev_owned_state["player"],
                "location": attacking_player_location,
            })
        if self.shot_state is not None:
            self.publish_event({
                "type": "shot",
                "subtype": "saved" if attacking_player["short_position"] == "GK" else "missed",
                "team": self.shot_state["team"],
                "player": self.shot_state["player"],
                "goalkeeper": attacking_player if attacking_player["short_position"] == "GK" else None,
                "location": self.shot_state["location"],
                "seconds_interval": int(self.match_time - self.shot_state["match_time"]),
            })
            self.shot_state = None
        
        # Capture the first action of two-step events
        if self.is_pass(attacking_action):
            self.pass_state = {
                "type": "pass",
                "subtype": attacking_action,
                "match_time": self.match_time,
                "team": attacking_team["name"],
                "player": attacking_player,
                "location": attacking_player_location,
            }
        elif attacking_action == "shot":
            self.shot_state = {
                "type": "shot",
                "match_time": self.match_time,
                "team": attacking_team["name"],
                "player": attacking_player,
                "location": attacking_player_location,
            }
        self.prev_obs = obs
        self.prev_owned_state = {
            "team": attacking_team["name"],
            "player": attacking_player,
            "location": attacking_player_location,
        }
