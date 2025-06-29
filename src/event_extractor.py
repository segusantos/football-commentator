import json
from time import perf_counter
from datetime import datetime
from enum import Enum
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
        self.teams = json.load(open("/gfootball/teams.json", "r"))
        self.min_inactivity_time = 0.5
        self.max_inactivity_time = 5.0
        self.last_event_time = None
        self.prev_obs = None

        self.potential_event = None

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
    
    def send_event(self) -> None:
        # type
        # subtype
        # timestamp
        # time_interval
        # team_in_possession
        self.last_event_time = perf_counter()

    def process_state(self, obs: dict, left_action: str, right_action: str) -> None:
        # First step
        if self.prev_obs is None:
            # Primer evento -> algo de contexto del partido
            return

        # Last step
        if obs["steps_left"] == 0:
            # Último evento -> se terminó el partido
            return

        # Irrelevant step
        elif (left_action == "idle" and right_action == "idle") or \
            obs["ball_owned_team"] == -1 or \
            self.is_directional(left_action) or self.is_directional(right_action):
            return

        # State machine
        # Revisar cuáles son info para después y cuáles son -> Mandá un nuevo event
        event = {}

        # Game Events
        if obs["score"] != self.prev_obs["score"]:
            # Goal event -> debería venir de un evento de shot o algo así
            pass
        elif obs["game_mode"] not in [self.prev_obs["game_mode"], GameMode.NORMAL]:
            # Game mode change event
            pass
        elif not np.array_equal(obs["left_team_yellow_card"], self.prev_obs["left_team_yellow_card"]) or \
           not np.array_equal(obs["right_team_yellow_card"], self.prev_obs["right_team_yellow_card"]):
            # Yellow card event
            pass
        elif not np.array_equal(obs["right_team_active"], self.prev_obs["right_team_active"]) or \
           not np.array_equal(obs["right_team_active"], self.prev_obs["right_team_active"]):
            # Red card event
            pass

        # Attack Events
        elif left_action == "shot" or right_action == "shot":
            # Guardar información acerca del disparo para poder recuperar después si:
            # - Es gol
            # - Fue atajado
            # - Fue errado
            pass
        elif "pass" in left_action or "pass" in right_action:
            # Guardar información acerca del pase para después recuperar si:
            # - Fue interceptado
            # - Fue completado/exitoso
            pass

        # Posession Events
        elif obs["ball_owned_team"] != self.prev_obs["ball_owned_team"]:
            # Cambio de posesión
            # Si el balón es del equipo contrario, entonces se perdió la posesión
            # Si el balón es del equipo propio, entonces se ganó la posesión
            pass
        elif left_action == "sliding" or right_action == "sliding":
            # Guardar información por si termina siendo foul o cambio de posesión
            pass
        elif perf_counter() - self.last_event_time > self.max_inactivity_time:
            # Si pasó mucho tiempo y no cambió la posesión (si no se mandó un evento por mucho tiempo)
            # se podría hacer un evento que recalque esto (se fije si el que conduce está sprint o dribble)
            pass

        if event:
            self.send_event(event)
        self.prev_obs = obs
        return
