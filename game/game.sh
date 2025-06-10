xhost +local:docker
docker run -it \
    -v /tmp/.X11-unix:/tmp/.X11-unix:rw \
    -e DISPLAY=$DISPLAY \
    --gpus all \
    --device /dev/snd:/dev/snd \
    -v /dev/dri:/dev/dri \
    -e PULSE_SERVER=unix:/tmp/pulse/native \
    -v /run/user/$(id -u)/pulse:/tmp/pulse:ro \
    -v ~/.config/pulse/cookie:/root/.config/pulse/cookie:ro \
    -v ./src:/gfootball \
    game python3 /gfootball/game.py --action_set=full
