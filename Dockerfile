FROM nvidia/cuda:12.2.0-runtime-ubuntu20.04

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update && apt-get --no-install-recommends install -yq git cmake build-essential \
    libgl1-mesa-dev libsdl2-dev \
    libsdl2-image-dev libsdl2-ttf-dev libsdl2-gfx-dev libboost-all-dev \
    libdirectfb-dev libst-dev mesa-utils xvfb x11vnc \
    python3-pip

RUN python3 -m pip install --upgrade pip "setuptools<58" wheel
RUN python3 -m pip install psutil
RUN python3 -m pip install six
RUN python3 -m pip install evdev

WORKDIR /football
COPY /football .
RUN python3 -m pip install .
