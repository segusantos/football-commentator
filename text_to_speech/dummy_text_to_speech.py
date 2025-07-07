import logging
import os
import random
import time
import subprocess
import tempfile
from proto import data_pb2  # type: ignore

logger = logging.getLogger(__name__)

# Create a similar class for the actual implementation
# Then update the import in the server.py file
class TextToAudio:
    """Simulates text-to-speech synthesis and returns dummy audio bytes."""

    def process(self, text_request: data_pb2.Comment) -> bytes:
        """Return raw bytes of a short WAV clip bundled with the module.

        This keeps the example self-contained while allowing Module D to
        play *real* audio instead of random bytes. The method still waits a
        random delay to mimic TTS latency.
        """

        logger.info(f"🗣️  Synthesizing (id={text_request.id})")

        # Use espeak-ng via helper to synthesise speech to a temporary WAV.
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
            wav_path = tmp_wav.name

        self.tts_espeak(text_request.text, wav_path=wav_path)

        try:
            with open(wav_path, "rb") as fp:
                audio_bytes = fp.read()
        except FileNotFoundError:
            logger.error("TTS output file not found at %s", wav_path)
            audio_bytes = b""  # return empty on failure to keep pipeline alive
        finally:
            # Clean up temp file
            try:
                os.remove(wav_path)
            except OSError:
                pass

        return audio_bytes
    
    def tts_espeak(self, text, wav_path="output.wav", voice="en-us", rate=175):
        """
        Use espeak-ng to convert text to speech and save it as a .wav file.

        :param text: Text to convert to speech
        :param wav_path: Output file path for the .wav file
        :param voice: Voice language (e.g., 'en-us', 'es-la')
        :param rate: Speed of speech (default 175)
        """
        cmd = [
            "espeak-ng",
            "-v", voice,
            "-s", str(rate),
            "-w", wav_path,
            text
        ]
        
        result = subprocess.run(cmd, capture_output=True)
        
        if result.returncode == 0:
            logger.info(f"✅ Generated audio for text:\n{text[:90]}...")
            # logger.info(f"✅ Saved to {wav_path}")
        else:
            logger.error(f"❌ Error: {result.stderr.decode()}")