# Football Commentator

A real-time automatic football commentary generation system using natural language processing and a distributed microservices architecture.

[![Python 3.11.13](https://img.shields.io/badge/python-3.11.13-blue.svg)](https://www.python.org/downloads/)

<div align="center">
<img src="assets/logo.png" alt="Football Commentator" height="200"/>
</div>

## Overview

Football Commentator is a distributed system that generates real-time Spanish commentary for football matches simulated in a modified Google Research Football environment. The system features custom visual modifications representing the 2022 FIFA World Cup Final between Argentina and France.

### Key Features

- **Real-time Event Extraction**: Processes Google Research Football simulation data to identify meaningful game events
- **Intelligent Commentary Generation**: Converts events to natural language using GPT-4.1 nano or fine-tuned Gemma models  
- **High-Quality Speech Synthesis**: Generates Argentine Spanish commentary using fine-tuned Coqui TTS (xTTSv2)
- **Distributed Architecture**: Microservices communicate via gRPC with automatic service discovery
- **Custom World Cup Theme**: Modified GFootball environment with Argentina vs France 2022 World Cup Final visuals
- **Controller Support**: Play using Xbox/PlayStation controllers with full device forwarding in Docker

<div align="center">
<img src="assets/football_commentator.png" alt="Football Commentator Architecture" height="400"/>
</div>

## Architecture

The system follows a microservices architecture with five main components communicating through gRPC:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐    ┌──────────────┐
│ Event Extractor │───►│ Event To Text    │───►│ Text To Speech  │───►│ Audio Player │
│                 │    │                  │    │                 │    │              │
│ - GFootball     │    │ - GPT-4/Gemma    │    │ - xTTSv2        │    │ - PyAudio    │
│ - Event Logic   │    │ - Context Mgmt   │    │ - Voice Cloning │    │ - Buffering  │
└─────┬───────────┘    └─────────┬────────┘    └─────────┬───────┘    └──────┬───────┘
      │                          │                       │                   │
      │              ┌──────────────────┐                │                   │
      └─────────────►│ Discovery Service│◄───────────────┼───────────────────┘
                     │                  │◄───────────────┘
                     │ - Service Reg.   │
                     │ - Health Checks  │
                     └──────────────────┘
```

### Component Details

The architecture is designed to handle real-time data processing and commentary generation on consumer-grade GPU hardware. The modules are designed to be executed on separate machines, each with its own GPU, and communicate through gRPC over LAN for optimal performance.

#### Event Extractor
- Uses a modified version of the [Google Research Football](https://github.com/google-research/football) reinforcement learning environment with custom Argentina vs France 2022 World Cup Final visuals (jerseys, shields, branding)
- Extracts meaningful events (passes, shots, goals, fouls, etc.) from raw observations and actions data
- Supports controller input for manual gameplay
- Publishes events via gRPC to downstream services

#### Event To Text
- Converts extracted events into natural language commentary text
- Uses either GPT-4.1 nano or a local Gemma 3 model fine-tuned on GPT-4 outputs
- Generates coherent and contextually relevant Spanish commentary
- Maintains game context and commentary coherence across events
- Handles event batching for optimal processing

#### Text To Speech
- Converts generated text commentary into speech using a fine-tuned xTTSv2 model
- Built on [marianbasti/XTTS-v2-argentinian-spanish](https://huggingface.co/marianbasti/XTTS-v2-argentinian-spanish) and further adapted using transcribed Argentine football commentary
- Multi-speaker voice cloning capabilities from professional football commentators
- Chunk-based processing for optimal audio quality
- 16-bit PCM WAV output at native sample rates

#### Audio Player
- Handles real-time audio playbook with buffering for smooth playback
- Ambient stadium sound mixing for immersive experience
- Low-latency audio pipeline using PyAudio
- Can be run on the same machine as Event Extractor or separately

#### Discovery Service
- FastAPI-based service registry that facilitates identification between system components
- Automatic service registration and health checking for distributed deployment
- Enables modules running on separate machines to find and communicate with each other via gRPC
- Load balancing and failover support for production environments

## Installation

### Prerequisites

- Python 3.11.13
- CUDA-compatible GPU (recommended)
- Docker (for the event extractor module)
- 16GB+ RAM recommended

### Quick Start

1. **Clone the repository**:
```bash
git clone https://github.com/segusantos/football-commentator.git
cd football-commentator
```

2. **Build the Event Extractor Docker container**:
```bash
cd event_extractor
docker build -t gfootball .
cd ..
```

3. **Install Python dependencies for other modules**:
```bash
# Install dependencies for each module
pip install -r event_extractor/requirements.txt
pip install -r event_to_text/requirements.txt  
pip install -r text_to_speech/requirements.txt
pip install -r audio_player/requirements.txt
pip install -r discovery/requirements.txt
```

### GPU and Display Setup

For GPU acceleration and visual rendering with the event extractor:

```bash
# Enable X11 forwarding (Linux)
xhost +local:docker
```

The event extractor automatically detects connected controllers and runs the game in Docker with proper device forwarding.

## Configuration

The system uses environment variables for configuration:

### Discovery Service
```bash
export DISCOVERY_URL="http://localhost:8000"
export DISCOVERY_API_KEY="your-secret-token"
```

### Event To Text
```bash
# For GPT-4 usage
export OPENAI_API_KEY="your-openai-key"
```

### Module Communication
```bash
# Auto-discovered by default, but can be manually configured
export MODULE_B_HOST="localhost:50052"  # Event-to-text service
export MODULE_C_HOST="localhost:50053"  # Text-to-speech service  
export MODULE_D_HOST="localhost:50054"  # Audio player service
```

## Usage

Start the system components in the following order:

```bash
# 1. Discovery service (service registry)
python -m discovery.run

# 2. Audio player 
python -m audio_player.run

# 3. Text-to-speech
python -m text_to_speech.run

# 4. Event-to-text
python -m event_to_text.run

# 5. Event extractor (starts the World Cup game)
python -m event_extractor.run
```

The system supports Xbox 360, PlayStation controllers automatically for manual control of one or both teams.

## Project Structure

```
football-commentator/
├── discovery/              # Service discovery and registration
│   ├── client.py           # Discovery client SDK
│   ├── server.py           # FastAPI discovery service
│   └── run.py              # Service entry point
├── event_extractor/        # Game simulation and event extraction
│   ├── football/           # Modified Google Research Football
│   └── src/                # Event processing logic
│       ├── event_extractor.py
│       ├── send_event.py
│       └── commentate_game.py
├── event_to_text/          # NLP commentary generation
│   ├── event_to_text.py    # GPT-4/Gemma integration
│   └── run.py              # gRPC service
├── text_to_speech/         # Speech synthesis
│   ├── text_to_speech.py   # xTTSv2 implementation
│   ├── model/              # Fine-tuned Argentine model
│   └── dataset_coqui/      # Training data
├── audio_player/           # Audio output and mixing
├── proto/                  # Protocol buffer definitions
├── utils/                  # Shared utilities
└── game/                   # Standalone game runner
```

## Authors

This project was developed as the final project for the **I400 Natural Language Processing** course at [Universidad de San Andrés](https://www.udesa.edu.ar/), Argentina, by:

- **Marcos Piotto** (mpiotto@udesa.edu.ar)
- **Segundo Santos Torrado** (ssantostorrado@udesa.edu.ar)  
- **Ignacio Schuemer** (ischuemer@udesa.edu.ar)
- **Santiago Tomas Torres** (storres@udesa.edu.ar)
