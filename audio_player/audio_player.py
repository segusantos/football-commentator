import logging
import threading
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
import io
import wave
import simpleaudio as sa
import platform

logger = logging.getLogger(__name__)

class OrderedAudioPlayer:
    """Ensures audio is played sequentially in ascending id order regardless of arrival order.

    The first arriving request defines the starting ID; thereafter playback
    proceeds strictly in ascending order (id, id+1, …).
    """

    def __init__(self, min_duration: float = 1.0, max_duration: float = 2.0):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self._pending: dict[int, bytes] = {}
        self._next_id: int | None = None  # will be set when first audio arrives
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        # single thread executor to guarantee sequential playback
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._executor.submit(self._worker)

    def process(self, req_id: str, audio: bytes):
        """Enqueue audio; playback starts when its turn comes."""
        try:
            audio_id = int(req_id)
        except ValueError:
            logger.warning("Received non-integer id '%s', playing immediately", req_id)
            audio_id = self._next_id  # best effort
        with self._not_empty:
            # record first id as the starting point
            if self._next_id is None:
                self._next_id = audio_id

            if audio_id in self._pending:
                logger.warning("Duplicate audio id=%s received, overwriting", audio_id)
            self._pending[audio_id] = audio
            self._not_empty.notify()

    # ---------------------------------------------------------------------
    # internal
    # ---------------------------------------------------------------------
    def _worker(self):
        while True:
            with self._not_empty:
                # wait until we have determined the starting id and the next
                # required id is present in the queue
                while self._next_id is None or self._next_id not in self._pending:
                    self._not_empty.wait()
                audio = self._pending.pop(self._next_id)
                current_id = self._next_id
                self._next_id += 1
            logger.info(
                f"🔊 Playing audio (id={current_id}) {len(audio)} bytes…"
            )
            try:
                if "WSL" in platform.uname().release:
                    raise RuntimeError("skip simpleaudio")  # force fallback immediately
                with io.BytesIO(audio) as buf:
                    with wave.open(buf, "rb") as wav:
                        frames = wav.readframes(wav.getnframes())
                        play_obj = sa.play_buffer(
                            frames,
                            num_channels=wav.getnchannels(),
                            bytes_per_sample=wav.getsampwidth(),
                            sample_rate=wav.getframerate(),
                        )
                        play_obj.wait_done()
            except Exception as exc:
                logger.error("❌ Audio playback via simpleaudio failed: %s", exc)
                # ------------------------------------------------------------------
                # Fallback: attempt playback via `paplay` (PulseAudio) – useful on
                # WSL where ALSA default device is often missing but PulseAudio
                # works out-of-the-box (e.g. with WSLg).
                # ------------------------------------------------------------------
                try:
                    with tempfile.NamedTemporaryFile(suffix=".wav", delete=True) as tmp_wav:
                        tmp_wav.write(audio)
                        tmp_wav.flush()
                        subprocess.run(["paplay", "--rate=2", tmp_wav.name],
                                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                        logger.info(f"✅ Fallback paplay succeeded for audio (id={current_id})")
                except FileNotFoundError:
                    logger.error("❌ paplay command not found - install pulseaudio-utils to enable fallback")
                except subprocess.CalledProcessError as sub_exc:
                    logger.error("❌ paplay failed: %s", sub_exc)
            logger.info(f"✅ Finished playing audio (id={current_id})") 
