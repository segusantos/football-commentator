"""module_c.text_to_speech
---------------------------------
An XTTS wrapper that **accepts a local model directory** (via env-vars
`XTTS_MODEL_DIR` and `XTTS_TOKENIZER_PATH`) for fine-tuned models.

* Works with XTTS-v2 fine-tuned models
* Implements text chunking for better processing
* Saves 16-bit PCM WAV using the model's native sample rate
"""

from io import BytesIO
import logging
import os
from pathlib import Path
from typing import List
import re

import numpy as np
import soundfile as sf
import torch
from TTS.tts.configs.xtts_config import XttsConfig
from TTS.tts.models.xtts import Xtts
from TTS.tts.layers.xtts.tokenizer import VoiceBpeTokenizer

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

# -----------------------------------------------------------------------------
# Environment variables for XTTS model paths
# XTTS_MODEL_DIR = Path(os.getenv("XTTS_MODEL_DIR", 
#     "run/training/GPT_XTTS_v2.0_Soccer_Commentary_FT-July-04-2025_05+04AM-7b4f690")).expanduser()
# XTTS_TOKENIZER_PATH = Path(os.getenv("XTTS_TOKENIZER_PATH", 
#     "/home/san/Documents/Ingenieria UdeSA/NLP/Relator_futbol_NLP/TTS/XTTS-v2-argentinian-spanish/vocab.json")).expanduser()
# XTTS_SPEAKER_WAV = os.getenv("XTTS_SPEAKER_WAV", "data/dataset_coqui/wavs/02_65.wav")

XTTS_MODEL_DIR = Path("module_c").expanduser()
XTTS_TOKENIZER_PATH = Path("module_c/vocab.json").expanduser()
XTTS_SPEAKER_WAV = Path("module_c/00005.wav").expanduser()
# Text chunking parameters
MAX_CHUNK_LENGTH = 200  # characters
# -----------------------------------------------------------------------------

class TextToAudio:
    """Turn Spanish commentary into 16-bit PCM WAV bytes using XTTS."""

    def __init__(self, voice: str = None, sample_rate: int = None):
        # voice parameter kept for interface compatibility but not used in XTTS
        self.voice = voice
        self.sample_rate = sample_rate  # Will be overridden by model's native rate
        
        # Load XTTS model
        self._load_model()
        
        # Update sample rate from model config
        self.sample_rate = self.config.audio.output_sample_rate
        logger.info("📦 XTTS model loaded with sample rate: %d Hz", self.sample_rate)

    def _load_model(self):
        """Load the XTTS model and configuration."""
        config_path = XTTS_MODEL_DIR / "config.json"
        
        if not config_path.exists():
            raise FileNotFoundError(f"XTTS config not found: {config_path}")
        if not XTTS_TOKENIZER_PATH.exists():
            raise FileNotFoundError(f"XTTS tokenizer not found: {XTTS_TOKENIZER_PATH}")
        
        # Load config
        self.config = XttsConfig()
        self.config.load_json(str(config_path))
        
        # Fix tokenizer path
        self.config.model_args.tokenizer_file = str(XTTS_TOKENIZER_PATH.resolve())
        
        # Build model and load weights
        self.model = Xtts.init_from_config(self.config)
        self.model.load_checkpoint(self.config, checkpoint_dir=str(XTTS_MODEL_DIR), eval=True)
        
        # Reinitialize tokenizer after loading checkpoint
        self.model.tokenizer = VoiceBpeTokenizer(self.config.model_args.tokenizer_file)
        
        # Send to GPU and eval mode
        if torch.cuda.is_available():
            self.model.cuda()
        self.model.eval()
        
        logger.info("📦 Loaded XTTS from %s", XTTS_MODEL_DIR)
        logger.info("🎤 Using speaker reference: %s", XTTS_SPEAKER_WAV)

    def _chunk_text(self, text: str) -> List[str]:
        """Split text into chunks suitable for XTTS processing."""
        # Clean and normalize text
        text = text.strip()
        if not text:
            return []
        
        # If text is short enough, return as single chunk
        if len(text) <= MAX_CHUNK_LENGTH:
            return [text]
        
        chunks = []
        
        # Split by sentences first (period, exclamation, question mark)
        sentences = re.split(r'([.!?]+)', text)
        
        current_chunk = ""
        for i in range(0, len(sentences), 2):  # Process sentence + punctuation pairs
            sentence = sentences[i].strip()
            punct = sentences[i + 1] if i + 1 < len(sentences) else ""
            
            if not sentence:
                continue
                
            full_sentence = sentence + punct
            
            # If adding this sentence would exceed max length, save current chunk
            if current_chunk and len(current_chunk) + len(full_sentence) > MAX_CHUNK_LENGTH:
                chunks.append(current_chunk.strip())
                current_chunk = full_sentence
            else:
                current_chunk += (" " if current_chunk else "") + full_sentence
        
        # Add remaining chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # If we still have chunks that are too long, split them further
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= MAX_CHUNK_LENGTH:
                final_chunks.append(chunk)
            else:
                # Split by commas or spaces as last resort
                words = chunk.split()
                temp_chunk = ""
                for word in words:
                    if temp_chunk and len(temp_chunk) + len(word) + 1 > MAX_CHUNK_LENGTH:
                        final_chunks.append(temp_chunk.strip())
                        temp_chunk = word
                    else:
                        temp_chunk += (" " if temp_chunk else "") + word
                if temp_chunk.strip():
                    final_chunks.append(temp_chunk.strip())
        
        return final_chunks

    @staticmethod
    def _to_np(audio_tensor):
        """Convert XTTS output to numpy array."""
        if isinstance(audio_tensor, torch.Tensor):
            return audio_tensor.squeeze().cpu().numpy().astype(np.float32, copy=False)
        if isinstance(audio_tensor, np.ndarray):
            return audio_tensor.astype(np.float32, copy=False)
        raise TypeError(f"Unexpected audio type: {type(audio_tensor)}")

    def _synthesize_chunk(self, text: str) -> np.ndarray:
        """Synthesize a single text chunk using XTTS."""
        try:
            output = self.model.synthesize(
                text,
                self.config,
                speaker_wav=XTTS_SPEAKER_WAV,
                gpt_cond_len=3,
                language="es",
            )
            
            wav = output["wav"]
            return self._to_np(wav)
            
        except Exception as e:
            logger.error("❌ Error synthesizing chunk '%s': %s", text[:50], str(e))
            # Return silence as fallback
            return np.zeros(int(0.5 * self.sample_rate), dtype=np.float32)

    def _collect(self, text: str) -> np.ndarray:
        """Process text in chunks and collect audio."""
        chunks = self._chunk_text(text)
        
        if not chunks:
            logger.warning("⚠️  No text chunks to process")
            return np.empty(0, np.float32)
        
        audio_chunks: List[np.ndarray] = []
        
        for idx, chunk in enumerate(chunks):
            logger.debug("    chunk %-2d: %s", idx, chunk[:50] + "..." if len(chunk) > 50 else chunk)
            
            audio = self._synthesize_chunk(chunk)
            audio_chunks.append(audio)
            
            # Add small pause between chunks (100ms)
            if idx < len(chunks) - 1:  # Don't add pause after last chunk
                pause = np.zeros(int(0.1 * self.sample_rate), dtype=np.float32)
                audio_chunks.append(pause)
        
        return np.concatenate(audio_chunks) if audio_chunks else np.empty(0, np.float32)

    def process(self, request) -> bytes:
        """Process text request and return WAV bytes."""
        text = request.text if hasattr(request, "text") else str(request)
        
        # Clean text
        text = text.strip()
        if not text:
            raise ValueError("Empty text provided")
        
        # Ensure text ends with punctuation for better synthesis
        if not text.endswith((".", "!", "?", "\n")):
            text += "."
        
        logger.info("🗣️  Synthesising | %s…", text[:70])
        
        audio = self._collect(text)
        
        if audio.size == 0:
            raise RuntimeError("XTTS produced no audio")
        
        # Check if audio is too short (likely a problem)
        min_duration = 0.1  # 100ms minimum
        if audio.shape[0] < min_duration * self.sample_rate:
            logger.warning("⚠️  Very short audio output (%.0f ms). This might indicate a problem.",
                           1000 * audio.shape[0] / self.sample_rate)
        
        duration = audio.shape[0] / self.sample_rate
        logger.info("✅ Final audio %.2f s (%d samples)", duration, audio.shape[0])
        
        # Convert to 16-bit PCM WAV
        buf = BytesIO()
        sf.write(buf, audio, self.sample_rate, format="WAV", subtype="PCM_16")
        return buf.getvalue()