# ⚽ AI Football Commentator

A distributed system for real-time football match commentary generation using natural language processing.

## Overview

This project is a **proof of concept** for generating live football commentary without human intervention. It leverages structured match data from a simulation environment, converts it into natural language using AI models, and synthesizes realistic voice narration, mimicking the tone and emotion of professional commentators.

> ⚠️ Real video-based event detection is out of scope for this version. We use **Google Research Football** to simulate matches and extract precise event data.


(video o link a un video de demo)

## 🛠️ Architecture

The system is modular and can be distributed across multiple machines:

### 📍 1. Event Extractor

* Simulates a football match using **Google Research Football**.
* Extracts relevant events from the simulation raw data.
* Emits structured events asynchronously via `gRPC`.

### ✍️ 2. Event-to-Text Generator

* Receives structured events and generates natural-language descriptions.
* Used OpenAI's GPT-4o model to first generate a synthetic dataset of event-commentary pairs.
* Then fine-tuned a small model to match the accuracy of the GPT-4o model and be able to run locally in real-time.
* Mimics the narrative style of well-known Spanish football commentators.

### 🔊 3. Text-to-Speech (TTS)

* Converts text into expressive voice using [xTTS-v2 (Coqui TTS)](https://github.com/coqui-ai/TTS), fined-tuned on a dataset of short audio clips from Argentinian football commentators.
* Outputs audio that matches the excitement and rhythm of live match broadcasts.

## 🌐 Communication

* Modules run independently and communicate over LAN using **gRPC**.
* Low-latency performance: \~2 seconds from event trigger to audio playback.





## 🚀 Getting Started

> Setup instructions coming soon.

<!-- tendria que ser algo como usar un requirements.txt general y dps por modulo otro requirements.txt ? -->

### Module A

### Module B

### Module C

### Module D




<!-- (esto esta viejo pero sirve de referencia) -->

### Multi-Module gRPC Pipeline with Service Discovery (A → B → C → D)

```
Module A  →  Module B  →  Module C  →  Module D
(events)     (text)        (audio)      (playback)
```

Each service is placed in its own folder (`module_a/ … module_d/`) and communicates with the next service using the messages and services defined in `proto/data.proto`.

### 🆕 Service Discovery

The system includes a **FastAPI-based service discovery service** that eliminates the need for manual endpoint configuration. Services can:
- **Auto-register** themselves when they start
- **Discover** other services dynamically  
- Work across **different machines and networks**
- **Pure discovery-based** communication (no manual configuration needed)
- **Graceful shutdown** with automatic service unregistration
- **Simplified networking** with explicit IP control via `SERVICE_HOST_IP`
- **Clean logging** with module identification and verbosity control
- **🔒 API Key Authentication** to prevent unauthorized access and spam

---
## 1. Quick Start

### Option A: With Service Discovery (Recommended)

1.  Install dependencies (inside a fresh virtual-env):
    ```bash
    pip install -r requirements.txt
    ```

2.  Start the **Discovery Service** (on the machine that will act as the registry):
    ```bash
    python -m discovery.server
    ```
    The discovery service will start on `http://0.0.0.0:8000`

3.  Configure discovery (copy and modify env.example):
    ```bash
    cp .env.example .env
    # Edit .env to set:
    # - DISCOVERY_URL: where the discovery server is running
    # - DISCOVERY_API_KEY: secure API key for authentication
    ```

4.  Start the services (all now use discovery):
        
    **Manual way (separate terminals):**
    ```bash
    # Terminal 1
    python -m module_d.server
    # Terminal 2  
    python -m module_c.server
    # Terminal 3
    python -m module_b.server_with_discovery
    ```

5.  Trigger the pipeline:
    ```bash
    python -m module_a.dummy_play_game
    ```

### Option B: Without Discovery 

In the env file set `MODULE_B_HOST`, `MODULE_C_HOST`, `MODULE_D_HOST` to the address of the machine you are running each service on.



### 2. Service Discovery System

#### How it Works

The discovery service acts as an **online dictionary** where:
- Services **register** themselves: `POST /register` with `{name, host, port, metadata}`
- Services **discover** others: `GET /discover/{service_name}` returns `{host, port, endpoint, metadata}`

### Discovery API Endpoints

| Method | Endpoint | Description | Authentication |
|--------|----------|-------------|----------------|
| `GET` | `/` | Health check and registry status | ❌ Public |
| `POST` | `/register` | Register a service | ✅ API Key Required |
| `GET` | `/discover/{name}` | Discover a service by name | ✅ API Key Required |
| `GET` | `/services` | List all registered services | ✅ API Key Required |
| `DELETE` | `/unregister/{name}` | Unregister a service | ✅ API Key Required |

### 🔒 Authentication

The discovery server uses **Bearer token authentication** with API keys to prevent unauthorized access:

- **Health check endpoint** (`/`) is public and requires no authentication
- **All other endpoints** require a valid API key in the `Authorization` header
- API keys are configured via the `DISCOVERY_API_KEY` environment variable
- Include the API key as: `Authorization: Bearer your-api-key-here`


### CLI Tool

Test the discovery service using the built-in CLI:

```bash
# Set your API key first (required for all operations)
export DISCOVERY_API_KEY=your-secure-api-key

# Register a service
python -m discovery.cli register my_service 8080 --metadata '{"version": "1.0"}'

# Discover a service  
python -m discovery.cli discover my_service

# List all services
python -m discovery.cli list

# Get just the endpoint
python -m discovery.cli endpoint my_service

# Unregister a service
python -m discovery.cli unregister my_service

# Use remote discovery server
python -m discovery.cli --discovery-url http://192.168.1.100:8000 list
```

### Environment Variables

**Discovery Configuration:**
```bash
DISCOVERY_HOST=localhost        # Discovery server location  
DISCOVERY_API_KEY=your-api-key  # API key for discovery server authentication
SERVICE_HOST_IP=192.168.1.100   # Override auto-detected IP (optional)
```

**Service Binding (optional):**
```bash
MODULE_B_HOST=0.0.0.0:50052     # Bind address for Module B
MODULE_C_HOST=0.0.0.0:50053     # Bind address for Module C
MODULE_D_HOST=0.0.0.0:50054     # Bind address for Module D
```

**Logging Configuration:**
```bash
VERBOSE=true                    # Enable detailed debug logs (default: false)
```

During local development you can place these keys in a `.env` file (they are loaded on every access via `scripts.utils.get_env_var`).
