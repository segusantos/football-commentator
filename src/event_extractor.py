from enum import Enum
import json
from time import sleep
import numpy as np


from send_event import EventSender


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


gameModeMap = {
    0: "normal",
    1: "saque_del_medio",
    2: "saque_de_arco",
    3: "tiro_libre",
    4: "corner",
    5: "lateral",
    6: "penal"
}


class EventExtractor:
    def __init__(self):
        # Load data
        self.metadata = json.load(open("/gfootball/metadata.json", "r"))

        # Match state
        self.total_steps = None
        self.match_time = 0.0
        self.event_cnt = 0
        self.goal_events = []
        self.card_events = []

        # Events metadata
        self.prev_obs = None
        self.prev_owned_state = None
        self.pass_state = None
        self.shot_state = None

        self.event_sender = EventSender()

        self.publish_event({
            "type": "inicio_del_partido",
            "match_metadata": self.metadata
        })

    def set_match_time(self, steps_left: int) -> str:
        self.match_time = 90 * 60 * (self.total_steps - steps_left) / self.total_steps

    def get_location_description(self, location: np.ndarray) -> str:
        x = (location[0] + FIELD_HALF_LENGTH) / (2 * FIELD_HALF_LENGTH)
        y = (location[1] + FIELD_HALF_WIDTH) / (2 * FIELD_HALF_WIDTH)
        if x < 3**-1:
            x_description = "tercio izquierdo de la cancha"
        elif 3**-1 <= x < 2 * 3**-1:
            x_description = "centro de la cancha (de izquierda a derecha)"
        else:
            x_description = "tercio derecho de la cancha"
        if y < 3**-1:
            y_description = "banda superior"
        elif 3**-1 <= y < 2 * 3**-1:
            y_description = "medio de la cancha (de arriba a abajo)"
        else:
            y_description = "banda inferior"
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

        self.event_sender.send_async(str(self.event_cnt), json.dumps(event, indent=4))

    def process_state(self, obs: dict, left_action: str, right_action: str) -> None:
        if obs["steps_left"] == 0:
            self.publish_event({
                "type": "fin_del_partido",
                "team_left": self.metadata["left_team"]["name"],
                "score_left": obs["score"][0],
                "team_right": self.metadata["right_team"]["name"],
                "score_right": obs["score"][1],
                "goal_events": self.goal_events,
                "card_events": self.card_events
            })
            sleep(10)
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
                "type": "gol",
                "subtype": "gol_en_contra" if self.shot_state is not None and self.shot_state["equipo"] != scoring_team["name"] else "gol",
                "anotador": self.shot_state["jugador"] if self.shot_state is not None else None,
                "ubicacion": self.shot_state["ubicacion"] if self.shot_state is not None else None,
                "equipo_anotador": scoring_team["name"],
                "team_left": self.metadata["left_team"]["name"],
                "score_left": obs["score"][0],
                "team_right": self.metadata["right_team"]["name"],
                "score_right": obs["score"][1],
            }
            self.goal_events.append(goal_event)
            self.publish_event(goal_event)
            self.shot_state = None
            sleep(10)
        if self.prev_obs is not None and not np.array_equal(obs["left_team_yellow_card"], self.prev_obs["left_team_yellow_card"]):
            for i, (prev_card, curr_card) in enumerate(zip(self.prev_obs["left_team_yellow_card"], obs["left_team_yellow_card"])):
                if curr_card and not prev_card:
                    player = self.metadata["left_team"]["players"][i]
                    card_event = {
                        "type": "tarjeta_amarilla",
                        "jugador": player,
                        "equipo": self.metadata["left_team"]["name"],
                    }
                    self.card_events.append(card_event)
                    self.publish_event(card_event)
        if self.prev_obs is not None and not np.array_equal(obs["right_team_yellow_card"], self.prev_obs["right_team_yellow_card"]):
            for i, (prev_card, curr_card) in enumerate(zip(self.prev_obs["right_team_yellow_card"], obs["right_team_yellow_card"])):
                if curr_card and not prev_card:
                    player = self.metadata["right_team"]["players"][i]
                    card_event = {
                        "type": "tarjeta_amarilla",
                        "jugador": player,
                        "equipo": self.metadata["right_team"]["name"],
                    }
                    self.card_events.append(card_event)
                    self.publish_event(card_event)
        if self.prev_obs is not None and not np.array_equal(obs["left_team_active"], self.prev_obs["left_team_active"]):
            for i, (prev_active, curr_active) in enumerate(zip(self.prev_obs["left_team_active"], obs["left_team_active"])):
                if not curr_active and prev_active:
                    player = self.metadata["left_team"]["players"][i]
                    card_event = {
                        "type": "tarjeta_roja",
                        "jugador": player,
                        "equipo": self.metadata["left_team"]["name"],
                    }
                    self.card_events.append(card_event)
                    self.publish_event(card_event)
        if self.prev_obs is not None and not np.array_equal(obs["right_team_active"], self.prev_obs["right_team_active"]):
            for i, (prev_active, curr_active) in enumerate(zip(self.prev_obs["right_team_active"], obs["right_team_active"])):
                if not curr_active and prev_active:
                    player = self.metadata["right_team"]["players"][i]
                    card_event = {
                        "type": "tarjeta_roja",
                        "jugador": player,
                        "equipo": self.metadata["right_team"]["name"],
                    }
                    self.card_events.append(card_event)
                    self.publish_event(card_event)
        if self.prev_obs is not None and obs["game_mode"] not in [GameMode.NORMAL, GameMode.KICKOFF] and obs["game_mode"] != self.prev_obs["game_mode"]:
            game_mode_event = {
                "type": "cambio_de_modo_de_juego",
                "modo_anterior": gameModeMap[self.prev_obs["game_mode"]],
                "modo_actual": gameModeMap[obs["game_mode"]],
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
        if self.pass_state is not None and self.pass_state["jugador"] != attacking_player:
            self.publish_event({
                "type": self.pass_state["type"],
                "subtype": self.pass_state["subtype"],
                "intervalo_segundos": int(self.match_time - self.pass_state["match_time"]),
                "equipo": self.pass_state["equipo"],
                "pasador": self.pass_state["jugador"],
                "ubicacion_pase": self.pass_state["ubicacion"],
                "receptor": attacking_player,
                "ubicacion_recepcion": attacking_player_location,
                "pase_completado": self.pass_state["equipo"] == attacking_team["name"],
            })
            self.pass_state = None
        elif self.prev_owned_state is not None and self.prev_owned_state["jugador"] != attacking_player:
            self.publish_event({
                "type": "cambio_de_posesion",
                "subtype": "mismo_equipo" if self.prev_owned_state["equipo"] == attacking_team["name"] else "equipo_diferente",
                "equipo_actual": attacking_team["name"],
                "equipo_anterior": self.prev_owned_state["equipo"],
                "jugador_actual": attacking_player,
                "jugador_anterior": self.prev_owned_state["jugador"],
                "ubicacion": attacking_player_location,
            })
        if self.shot_state is not None:
            self.publish_event({
                "type": "disparo",
                "subtype": "atajado" if attacking_player["short_position"] == "GK" else "fallado",
                "equipo": self.shot_state["equipo"],
                "jugador": self.shot_state["jugador"],
                "portero": attacking_player if attacking_player["short_position"] == "GK" else None,
                "ubicacion": self.shot_state["ubicacion"],
                "intervalo_segundos": int(self.match_time - self.shot_state["match_time"]),
            })
            self.shot_state = None
        
        # Capture the first action of two-step events
        if self.is_pass(attacking_action):
            self.pass_state = {
                "type": "pase",
                "subtype": attacking_action,
                "match_time": self.match_time,
                "equipo": attacking_team["name"],
                "jugador": attacking_player,
                "ubicacion": attacking_player_location,
            }
        elif attacking_action == "shot":
            self.shot_state = {
                "type": "disparo",
                "match_time": self.match_time,
                "equipo": attacking_team["name"],
                "jugador": attacking_player,
                "ubicacion": attacking_player_location,
            }
        self.prev_obs = obs
        self.prev_owned_state = {
            "equipo": attacking_team["name"],
            "jugador": attacking_player,
            "ubicacion": attacking_player_location,
        }
