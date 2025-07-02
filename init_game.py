import os
import subprocess
from evdev import list_devices, InputDevice


def getControllerPaths() -> list[str]:
    return [path for path in list_devices()
            if InputDevice(path).name in ["Wireless Controller", "Microsoft X-Box 360 pad"]]


def buildDockerCommand(controllerPaths: list[str]) -> list[str]:
    cmd = [
        "docker", "run", "-it",
        "-v", "/tmp/.X11-unix:/tmp/.X11-unix:rw",
        "-e", f"DISPLAY={os.environ['DISPLAY']}",
        "--gpus", "all",
        "--device", "/dev/snd:/dev/snd",
        "-v", "/dev/dri:/dev/dri",
        "-e", "PULSE_SERVER=unix:/tmp/pulse/native",
        "-v", f"/run/user/{os.getuid()}/pulse:/tmp/pulse:ro",
        "-v", f"{os.path.expanduser('~')}/.config/pulse/cookie:/root/.config/pulse/cookie:ro",
        "-v", "./src:/gfootball"
    ]
    for path in controllerPaths:
        cmd.extend(["--device", path])
    cmd.extend([
        "gfootball",
        "python3", "/gfootball/commentate_game.py",
        f"--player1={'gamepad:left_players=1' if len(controllerPaths) >= 1 else 'bot:left_players=1'}",
        f"--player2={'gamepad:right_players=1' if len(controllerPaths) == 2 else 'bot:right_players=1'}",
        # f"--player1={'gamepad:left_players=1' if len(controllerPaths) >= 1 else 'ppo2_cnn:left_players=1,policy=gfootball_impala_cnn,checkpoint=/gfootball/trained_model_11_vs_11_easy_stochastic'}",
        # f"--player2={'gamepad:right_players=1' if len(controllerPaths) == 2 else 'ppo2_cnn:right_players=1,policy=gfootball_impala_cnn,checkpoint=/gfootball/trained_model_11_vs_11_easy_stochastic'}",
    ])
    return cmd


def main() -> None:
    controllerPaths = getControllerPaths()
    assert len(controllerPaths) <= 2, "No more than 2 controllers are supported."
    cmd = buildDockerCommand(controllerPaths)
    subprocess.run(cmd)


if __name__ == "__main__":
    main()
