import logging
import threading
import subprocess
import tempfile
from concurrent.futures import ThreadPoolExecutor
import os
import time

logger = logging.getLogger(__name__)

class OrderedAudioPlayer:
    """Ensures audio is played sequentially in ascending id order regardless of arrival order.
    
    Optimized for Ubuntu 24.04 with PipeWire - avoids simpleaudio completely.
    """

    def __init__(self, min_duration: float = 1.0, max_duration: float = 2.0):
        self.min_duration = min_duration
        self.max_duration = max_duration
        self._pending: dict[int, bytes] = {}
        self._next_id: int | None = None  # will be set when first audio arrives
        self._lock = threading.Lock()
        self._not_empty = threading.Condition(self._lock)
        self._shutdown = False
        
        # Single thread executor to guarantee sequential playbook
        self._executor = ThreadPoolExecutor(max_workers=1)
        self._worker_future = self._executor.submit(self._worker)
        
        # Ambient sound playback
        self._ambient_sound_path = os.path.join(os.path.dirname(__file__), "ambient_sound.wav")
        self._ambient_process = None
        self._ambient_thread = None
        self._start_ambient_sound()
        
        logger.info("✅ OrderedAudioPlayer initialized (PipeWire mode)")

    def process(self, req_id: str, audio: bytes):
        """Enqueue audio; playback starts when its turn comes."""
        if self._shutdown:
            logger.warning("Player is shutting down, ignoring audio request")
            return
            
        try:
            audio_id = int(req_id)
        except ValueError:
            logger.warning("Received non-integer id '%s', using sequential ID", req_id)
            audio_id = self._next_id if self._next_id is not None else 0

        with self._not_empty:
            # Record first id as the starting point
            if self._next_id is None:
                self._next_id = audio_id
                logger.info(f"🎯 Starting sequence with ID {audio_id}")

            if audio_id in self._pending:
                logger.warning("Duplicate audio id=%s received, overwriting", audio_id)
            
            self._pending[audio_id] = audio
            logger.debug(f"📦 Queued audio ID {audio_id} ({len(audio)} bytes)")
            self._not_empty.notify()

    def shutdown(self):
        """Gracefully shutdown the player"""
        logger.info("🛑 Shutting down OrderedAudioPlayer...")
        self._shutdown = True
        
        # Stop ambient sound first
        self._stop_ambient_sound()
        
        with self._not_empty:
            self._not_empty.notify_all()
        
        # Wait for worker to finish
        try:
            self._worker_future.result(timeout=5.0)
        except Exception as e:
            logger.warning(f"Worker shutdown timeout: {e}")
        
        self._executor.shutdown(wait=True)
        logger.info("✅ OrderedAudioPlayer shutdown complete")

    def _worker(self):
        """Worker thread that plays audio in order"""
        logger.info("🎵 Audio worker thread started")
        
        while not self._shutdown:
            try:
                # Wait for next audio in sequence
                with self._not_empty:
                    while (not self._shutdown and 
                           (self._next_id is None or self._next_id not in self._pending)):
                        self._not_empty.wait(timeout=1.0)
                    
                    if self._shutdown:
                        break
                    
                    # Get the next audio to play
                    audio = self._pending.pop(self._next_id)
                    current_id = self._next_id
                    self._next_id += 1

                # Play the audio
                logger.info(f"🔊 Playing audio ID {current_id} ({len(audio)} bytes)")
                success = self._play_audio_pipewire(audio, current_id)
                
                if success:
                    logger.info(f"✅ Completed audio ID {current_id}")
                else:
                    logger.error(f"❌ Failed to play audio ID {current_id}")
                    
            except Exception as e:
                logger.error(f"❌ Worker error: {e}")
                logger.exception("Full exception details:")
                # Continue processing next audio instead of crashing
                continue

        logger.info("🎵 Audio worker thread stopped")

    def _play_audio_pipewire(self, audio: bytes, audio_id: int) -> bool:
        """
        Play audio using PipeWire (pw-play) - primary method for Ubuntu 24.04
        """
        temp_file = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav.write(audio)
                tmp_wav.flush()
                temp_file = tmp_wav.name

            # Play with pw-play
            result = subprocess.run(
                ["pw-play", "--volume=6.0", temp_file],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=30
            )
            
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(f"❌ Audio playback timeout for ID {audio_id}")
            return False
            
        except FileNotFoundError:
            logger.error("❌ pw-play not found - install pipewire-utils")
            return self._play_audio_fallback(audio, audio_id)
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ pw-play failed for ID {audio_id}: {e}")
            return self._play_audio_fallback(audio, audio_id)
            
        except Exception as e:
            logger.error(f"❌ Unexpected error playing audio ID {audio_id}: {e}")
            return self._play_audio_fallback(audio, audio_id)
            
        finally:
            # Clean up temporary file
            if temp_file:
                try:
                    os.unlink(temp_file)
                except:
                    pass

    def _play_audio_fallback(self, audio: bytes, audio_id: int) -> bool:
        """
        Fallback audio playback using paplay
        """
        temp_file = None
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_wav:
                tmp_wav.write(audio)
                tmp_wav.flush()
                temp_file = tmp_wav.name

            # Try paplay as fallback
            result = subprocess.run(
                ["paplay", "--volume=100000", temp_file],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                timeout=30
            )
            
            logger.info(f"✅ Fallback paplay succeeded for ID {audio_id}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Fallback paplay also failed for ID {audio_id}: {e}")
            return False
            
        finally:
            # Clean up temporary file
            if temp_file:
                try:
                    os.unlink(temp_file)
                except:
                    pass

    def _start_ambient_sound(self):
        """Start continuous ambient sound playback in a separate thread"""
        if not os.path.exists(self._ambient_sound_path):
            logger.warning(f"❌ Ambient sound file not found: {self._ambient_sound_path}")
            return
        
        logger.info(f"🎶 Starting ambient sound: {self._ambient_sound_path}")
        self._ambient_thread = threading.Thread(target=self._ambient_sound_worker, daemon=True)
        self._ambient_thread.start()
    
    def _stop_ambient_sound(self):
        """Stop ambient sound playback"""
        if self._ambient_process:
            try:
                self._ambient_process.terminate()
                self._ambient_process.wait(timeout=3.0)
                logger.info("🔇 Ambient sound stopped")
            except subprocess.TimeoutExpired:
                logger.warning("🔇 Ambient sound process killed (timeout)")
                self._ambient_process.kill()
            except Exception as e:
                logger.error(f"❌ Error stopping ambient sound: {e}")
            finally:
                self._ambient_process = None
    
    def _ambient_sound_worker(self):
        """Worker thread for continuous ambient sound playback"""
        logger.info("🎶 Ambient sound worker thread started")
        
        while not self._shutdown:
            try:
                # Start ambient sound process with loop and lower volume
                self._ambient_process = subprocess.Popen(
                    ["pw-play", "--volume=0.3", self._ambient_sound_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
                
                # Wait for process to finish or shutdown signal
                while not self._shutdown and self._ambient_process.poll() is None:
                    time.sleep(0.1)
                
                if self._shutdown:
                    break
                    
                # If process ended naturally, restart it (continuous loop)
                if self._ambient_process.poll() is not None:
                    logger.debug("🔄 Restarting ambient sound")
                    
            except FileNotFoundError:
                logger.error("❌ pw-play not found for ambient sound - trying fallback")
                self._ambient_sound_fallback()
                break
                
            except Exception as e:
                logger.error(f"❌ Ambient sound error: {e}")
                time.sleep(1.0)  # Wait before retry
                
        logger.info("🎶 Ambient sound worker thread stopped")
    
    def _ambient_sound_fallback(self):
        """Fallback ambient sound using paplay"""
        logger.info("🎶 Using paplay fallback for ambient sound")
        
        while not self._shutdown:
            try:
                self._ambient_process = subprocess.Popen(
                    ["paplay", "--volume=16384", self._ambient_sound_path],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE
                )
                
                # Wait for process to finish or shutdown signal
                while not self._shutdown and self._ambient_process.poll() is None:
                    time.sleep(0.1)
                
                if self._shutdown:
                    break
                    
                # If process ended naturally, restart it (continuous loop)
                if self._ambient_process.poll() is not None:
                    logger.debug("🔄 Restarting ambient sound (fallback)")
                    
            except Exception as e:
                logger.error(f"❌ Ambient sound fallback error: {e}")
                time.sleep(1.0)  # Wait before retry