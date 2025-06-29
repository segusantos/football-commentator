import json
from time import perf_counter


FIELD_HALF_LENGTH = 1.0
FIELD_HALF_WIDTH = 0.42
GOAL_HALF_WIDTH = 0.044


class PassExtractor:
    def __init__(self):
        teams = json.load(open("/gfootball/teams.json", "r"))
        self.left_team = teams["left_team"]
        self.right_team = teams["right_team"]

        self.pass_state = None
        self.pass_event = None
        self.pass_event_time = perf_counter()

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
    
    def is_kick(self, action: str) -> bool:
        return action == "shot" or self.is_pass(action)
    
    def is_pass(self, action: str) -> bool:
        return action in set([
            "short_pass",
            "long_pass",
            "high_pass"
        ])

    def get_location(self, x: float, y: float) -> str:
        norm_x = x / FIELD_HALF_LENGTH
        norm_y = y / FIELD_HALF_WIDTH
        if norm_x < -0.67:
            horizontal = "defensive third"
        elif norm_x < 0.33:
            horizontal = "middle third"
        else:
            horizontal = "attacking third"
        if norm_y < -0.33:
            vertical = "left wing"
        elif norm_y < 0.33:
            vertical = "center"
        else:
            vertical = "right wing"
        return f"{horizontal}, {vertical}"

    def process_state(self, obs: dict, left_action: str, right_action: str) -> None:
        if obs["ball_owned_team"] == -1:
            return
        
        team_id = obs["ball_owned_team"]
        current_team = self.left_team if team_id == 0 else self.right_team
        current_team_id = "left_team" if team_id == 0 else "right_team"
        action = left_action if team_id == 0 else right_action
        
        if self.is_pass(action):
            self.pass_state = {
                "type": "pass",
                "subtype": action,
                "timestamp": perf_counter(),
                "team_in_possession": current_team["name"],
                "player_in_possession": current_team["players"][obs["ball_owned_player"]],
                "location": self.get_location(obs[current_team_id][obs["ball_owned_player"]][0], obs[current_team_id][obs["ball_owned_player"]][1])
            }
        elif self.pass_state is not None \
            and self.pass_state["player_in_possession"] != current_team["players"][obs["ball_owned_player"]]:
            
            other_team = self.right_team if team_id == 0 else self.left_team
            player2 = current_team["players"][obs["ball_owned_player"]] if obs["ball_owned_team"] == team_id else other_team["players"][obs["ball_owned_player"]]
            
            self.pass_event = {
                "type": self.pass_state["type"],
                "subtype": self.pass_state["subtype"],
                "timestamp": perf_counter(),
                "time_interval": perf_counter() - self.pass_state["timestamp"],
                "team_in_possession": self.pass_state["team_in_possession"],
                "player1": self.pass_state["player_in_possession"],
                "player2": player2,
                "pass_completed": self.pass_state["team_in_possession"] == current_team["name"],
                "location_origin": self.pass_state["location"],
                "location_destination": self.get_location(obs[current_team_id][obs["ball_owned_player"]][0], obs[current_team_id][obs["ball_owned_player"]][1])
            }
            self.pass_state = None
            print(self.pass_event)
            print(perf_counter() - self.pass_event_time)
            self.last_event_time = perf_counter()
            self.pass_event = None
