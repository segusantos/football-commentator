import os
import time
import logging
import json
from datetime import datetime
from pathlib import Path
from openai import AzureOpenAI
from proto import data_pb2
from typing import List
from openai import OpenAI
import re


logger = logging.getLogger(__name__)


class EventToText:
    """NLP processing: converts batches of events to game commentary"""

    def __init__(self,
                 api_key: str = None,
                 endpoint: str = None,
                 deployment: str = None,
                 max_tokens: int = 50,  # Increased for batch processing
                 temperature: float = 0.7,
                 top_p: float = 0.9):
        # Load configuration from env if not provided
        self.api_key = api_key or os.getenv("API_KEY")
        self.endpoint = endpoint or os.getenv("ENDPOINT")
        self.deployment = deployment or os.getenv("DEPLOYMENT")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.top_p = top_p

        if not all([self.api_key, self.endpoint, self.deployment]):
            raise ValueError("Azure OpenAI API key, endpoint, and deployment must be set")

        # If the endpoint contains localhost, use OpenAI client
        if "localhost" in self.endpoint:
            logger.info("Using OpenAI client for local development")
            self.client = OpenAI(
                api_key=self.api_key,
                base_url=self.endpoint,
            )
        else:
            logger.info("Using Azure OpenAI client")
            self.client = AzureOpenAI(
                api_key=self.api_key,
                azure_endpoint=self.endpoint,
                api_version="2024-12-01-preview"
            )

        # Conversation history - keep last 5 exchanges (10 messages)
        self.conversation_history = []
        self.max_history_exchanges = 5

        # Debug logging setup
        self.debug_dir = Path("debug_llm_calls")
        self.debug_dir.mkdir(exist_ok=True)
        self.call_counter = 0

        self.max_commentary_interval = 10.0
        self.last_commentary_time = 0.0
        self.events_queue = []

        self.max_words = {
            "default": 3, 
            "inicio_del_partido": 20,  
            "fin_del_partido": 20,  
            "gol": 20, 
            "disparo": 5,
        }

        # System prompts
        time_interval = 1.0  # seconds
        self.system_prompts = {
            "default": (
                "Sos Mariano Closs, un relator de fútbol profesional argentino conocido por su estilo apasionado y dinámico. "
                "Recibirás eventos de partidos en formato JSON y tu tarea es generar un comentario breve y emocionante, "
                "agrupando los eventos provistos en un relato fluido que priorice según la importancia de los acontecimientos "
                f"del partido y la restricción de tiempo real. Por esta última razón, recibirás los eventos en lotes cada {time_interval} segundos. "
                f"De este modo, recibirás una secuencia de eventos del juego producida durante los últimos {time_interval} segundos. "
                f"Y deberás optar por generar un comentario de a lo sumo {time_interval} segundos de duración. Para ello, "
                f"debes restringirte a una oración por llamada y a un límite de palabra de {2*time_interval} palabras. "
                "Cuando simplemente cambia la posesión de la pelota, podés reducirte a nombrar al jugador que tiene la pelota, "
                "como por ejemplo: 'La tiene Messi', o simplemente 'Messi'. "
                "No repitas los comentarios de eventos anteriores. "
                "Todos tus comentarios deben ser en español rioplatense, según el estilo de Mariano Closs. "
                "Tu texto relatado luego será convertido a voz por un sintetizador de voz profesional (TTS). "
                "Tenés que ser MUY MUY MUY breve y conciso, transmitiendo solo lo más importante de cada conjuntos de eventos. "
            ),
            "inicio_del_partido": (
                "Sos Mariano Closs, un relator de fútbol profesional argentino conocido por su estilo apasionado y dinámico. "
                "Recibirás los metadatos de inicio de un partido de fútbol en formato JSON. "
                "Tu tarea es hacer una introducción EMOCIONANTE del partido que está por comenzar. "
                "Incluye: saludo inicial, presentación de los equipos, estadio, competición, y algún dato relevante. "
                "Genera una introducción CAUTIVANTE (máximo 5 oraciones de 20 segundos en total). "
                "Usa un tono profesional pero apasionado, típico del fútbol argentino. "
                "Todos tus comentarios deben ser en español rioplatense, según el estilo de Mariano Closs. "
                "Tu texto relatado luego será convertido a voz por un sintetizador de voz profesional (TTS). "
            ),
            "fin_del_partido": (
                "Sos Mariano Closs, un relator de fútbol profesional argentino conocido por su estilo apasionado y dinámico. "
                "Recibirás los metadatos de finalización de un partido de fútbol en formato JSON. "
                "Tu tarea es hacer un cierre EMOCIONANTE del partido que acaba de finalizar. "
                "Incluye: resumen del partido, resultado final, y algún dato relevante. "
                "Genera un cierre CAUTIVANTE (máximo 5 oraciones de 20 segundos en total). "
                "Usa un tono profesional pero apasionado, típico del fútbol argentino. "
                "Todos tus comentarios deben ser en español rioplatense, según el estilo de Mariano Closs. "
                "Tu texto relatado luego será convertido a voz por un sintetizador de voz profesional (TTS). "
            ),
            "gol": (
                "Sos Mariano Closs, un relator de fútbol profesional argentino conocido por su estilo apasionado y dinámico. "
                "Recibirás un evento de gol en formato JSON. "
                "Tu tarea es generar un comentario breve y emocionante sobre el gol, incluyendo: quién lo hizo, cómo fue la jugada, "
                "y la reacción del público. "
                "Genera un comentario CAUTIVANTE (máximo 3 oraciones de 10 segundos en total). "
                "Usa un tono profesional pero apasionado, típico del fútbol argentino. "
                "Todos tus comentarios deben ser en español rioplatense, según el estilo de Mariano Closs. "
                "Tu texto relatado luego será convertido a voz por un sintetizador de voz profesional (TTS). "
            )
        }

    def get_user_prompt(self, events: List[dict], n_words: int):
        events = [json.dumps(event, indent=4, ensure_ascii=False) for event in events]
        events_text = "\n\n---\n\n".join(events)
        return (
            "Instrucciones para el prompt que tenés que generar:\n\n"
            "Genera un relato resaltando los eventos más importantes en un comentario de "
            "relator de fútbol profesional argentino. Es muy importante que el "
            "relato sea fluido, emocionante y fácil de seguir para los oyentes en tiempo real."
            f"El relato debe ser de no más de {n_words} palabras ({n_words*2} segundos), "
            "y no debe repetir eventos anteriores. "
            "Es muy importante que respetes la restricción del número de palabras ya que "
            "el relato será convertido a voz por un sintetizador de voz profesional (TTS) "
            "en tiempo real y atrasarse implicaría que se arruine la experiencia de los oyentes. "
            "Si no lo respetás, serás castigado con la pena de muerte y no podrás relatar más partidos. "
            f"Secuencia de {len(events)} eventos del juego:\n\n{events_text}\n\n"





        )

    def generate_commentary(self, event_type: str) -> str:
        user_msg = self.get_user_prompt(self.events_queue, self.max_words.get(event_type, self.max_words["default"]))

        # Call Azure OpenAI with conversation history
        start = time.time()
        try:
            messages = self._build_messages(self.system_prompts.get(event_type, self.system_prompts["default"]), user_msg)
            response = self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                top_p=self.top_p,
            )
            latency = time.time() - start

            # Extract comment
            comment = response.choices[0].message.content.strip()

            # Add to conversation history
            self._add_to_conversation(user_msg, comment)

            # Save debug information
            self._save_debug_call(f"", messages, comment, latency)

            # Generate dataset entry
            dataset = self.gen_dataset(
                messages,
                comment,
                json_path="dataset.json"
            )

            # Log metrics
            logger.info(
                "[Module B] Processed batch of %d events in %.2f s (tokens: %s)",
                len(self.events_queue),
                latency,
                getattr(response.usage, 'total_tokens', None)
            )
            # Log prompt
            logger.info(f'  Comment:\n{comment}')

            self.events_queue.clear()
            self.last_commentary_time = time.time()
            return comment

        except Exception as e:
            logger.error(f"Error processing batch of {len(self.events_queue)} events: {str(e)}")

            self.events_queue.clear()
            return ""
        
    def process(self, event: data_pb2.Event) -> str:
        event = json.loads(event.data)
        self.events_queue.append(event)

        if time.time() - self.last_commentary_time > self.max_commentary_interval or \
            event["type"] in ["inicio_del_partido",
                             "fin_del_partido",
                             "gol",
                             "disparo",
                             "pelota_parada",
                             "pase"]:
            return self.generate_commentary(event["type"])
        return ""
    































    def gen_dataset(self, messages: List[dict], response: str, json_path: str) -> None:
        """
        Generate a dataset entry from messages and response and append it into a JSON array file.

        Each entry has the structure:
        {
            "input": "System prompt + all user messages",
            "output": "LLM response"
        }

        The JSON file at `json_path` will be maintained as a list of such entries.
        Leading occurrences of 'default\n' in the combined input are removed.
        """
        # 1) Extract and clean system prompt
        system_msgs = [m["content"] for m in messages if m.get("role") == "system"]
        system_text = system_msgs[0].strip() if system_msgs else ""

        # 2) Extract user messages
        user_texts = [m["content"].strip() for m in messages if m.get("role") == "user"]
        all_user_text = "\n".join(user_texts)

        # Combine, then strip unwanted default prefixes
        input_text = f"{system_text}\n\n{all_user_text}".strip()
        # Remove any leading 'default' lines
        input_text = re.sub(r"^default\s*\n+", "", input_text)

        entry = {
            "input": input_text,
            "output": response.strip()
        }

        # Load existing entries if any
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                entries = json.load(f)
                if not isinstance(entries, list):
                    entries = []
        except (FileNotFoundError, json.JSONDecodeError):
            entries = []

        # Append and write back
        entries.append(entry)
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(entries, f, ensure_ascii=False, indent=4)



    def _add_to_conversation(self, user_message: str, assistant_message: str):
        """Add a user-assistant exchange to conversation history."""
        self.conversation_history.append({"role": "user", "content": user_message})
        self.conversation_history.append({"role": "assistant", "content": assistant_message})
        
        # Keep only last N exchanges (N*2 messages)
        max_messages = self.max_history_exchanges * 2
        if len(self.conversation_history) > max_messages:
            self.conversation_history = self.conversation_history[-max_messages:]

    def _build_messages(self, system_prompt: str, user_message: str) -> List[dict]:
        """Build the complete message list with system prompt and conversation history."""
        messages = [{"role": "system", "content": system_prompt}]
        messages.extend(self.conversation_history)
        messages.append({"role": "user", "content": user_message})
        return messages

    def _save_debug_call(self, call_type: str, messages: List[dict], response_content: str, latency: float):
        """Save LLM call details to debug file."""
        self.call_counter += 1
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"llm_call_{self.call_counter:03d}_{call_type}.json"
        
        # Process messages to make embedded JSON readable
        readable_messages = []
        for msg in messages:
            readable_msg = msg.copy()
            if msg["role"] == "user" and ("evento del juego:" in msg["content"].lower() or "eventos del juego:" in msg["content"].lower()):
                readable_msg["content_formatted"] = self._format_user_content(msg["content"])
            readable_messages.append(readable_msg)
        
        debug_data = {
            "timestamp": timestamp,
            "call_number": self.call_counter,
            "call_type": call_type,
            "latency_seconds": latency,
            "messages_sent": readable_messages,
            "response_content": response_content,
            "conversation_history_length": len(self.conversation_history)
        }
        
        debug_file = self.debug_dir / filename
        with open(debug_file, 'w', encoding='utf-8') as f:
            json.dump(debug_data, f, indent=2, ensure_ascii=False)
        
        logger.debug(f"💾 Saved debug call to {filename}")

    def _format_user_content(self, content: str) -> dict:
        """Format user content to make embedded JSON events readable."""
        try:
            lines = content.split('\n')
            formatted_content = {
                "instruction": "",
                "events": [],
                "request": ""
            }
            
            current_section = "instruction"
            current_event_json = ""
            
            for line in lines:
                if line.strip().startswith('{"event_id"'):
                    if current_event_json:
                        # Parse previous event
                        try:
                            event_data = json.loads(current_event_json)
                            formatted_content["events"].append(event_data)
                        except:
                            formatted_content["events"].append({"raw": current_event_json})
                    current_event_json = line.strip()
                    current_section = "events"
                elif line.strip() == "---":
                    if current_event_json:
                        # Parse current event
                        try:
                            event_data = json.loads(current_event_json)
                            formatted_content["events"].append(event_data)
                        except:
                            formatted_content["events"].append({"raw": current_event_json})
                        current_event_json = ""
                elif line.strip().startswith("Genera un relato"):
                    if current_event_json:
                        # Parse last event
                        try:
                            event_data = json.loads(current_event_json)
                            formatted_content["events"].append(event_data)
                        except:
                            formatted_content["events"].append({"raw": current_event_json})
                        current_event_json = ""
                    formatted_content["request"] = line.strip()
                    current_section = "request"
                elif current_section == "instruction":
                    formatted_content["instruction"] += line + "\n"
            
            # Handle last event if exists
            if current_event_json:
                try:
                    event_data = json.loads(current_event_json)
                    formatted_content["events"].append(event_data)
                except:
                    formatted_content["events"].append({"raw": current_event_json})
            
            formatted_content["instruction"] = formatted_content["instruction"].strip()
            return formatted_content
            
        except Exception as e:
            return {"error": f"Failed to format content: {e}", "raw_content": content}
