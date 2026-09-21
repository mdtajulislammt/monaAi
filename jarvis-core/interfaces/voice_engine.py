"""Natural Bengali Voice Engine for JARVIS.

Integrates:
- STT: speech_recognition targeting 'bn-BD' with Google Speech Engine fallback.
- TTS: edge-tts ('bn-BD-PradeepNeural' male natural Bengali speech).
- Serialized, non-overlapping audio playback via system player (mpv/ffplay) or pygame.mixer.
"""
import asyncio
import logging
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


class BengaliVoiceEngine:
    """Production-grade Bengali voice engine for JARVIS."""

    def __init__(self):
        self.settings = get_settings()
        self._mixer_initialized = False
        self._stt_available = False
        self._recognizer = None
        self._microphone = None
        self._current_player_proc: Optional[subprocess.Popen] = None
        self._playback_lock = threading.Lock()
        self._stop_event = threading.Event()

        self._init_audio_mixer()
        self._init_speech_recognizer()

    @staticmethod
    def _suppress_c_stderr():
        """Context manager to suppress C-level ALSA stderr warnings during audio probing."""
        import contextlib
        @contextlib.contextmanager
        def _ctx():
            try:
                stderr_fd = os.dup(2)
                devnull = os.open(os.devnull, os.O_WRONLY)
                os.dup2(devnull, 2)
                try:
                    yield
                finally:
                    os.dup2(stderr_fd, 2)
                    os.close(devnull)
                    os.close(stderr_fd)
            except Exception:
                yield
        return _ctx()

    def _init_audio_mixer(self) -> None:
        """Initialize pygame.mixer safely if compiled."""
        try:
            with self._suppress_c_stderr():
                import warnings
                with warnings.catch_warnings():
                    warnings.simplefilter("ignore")
                    import pygame
                    if hasattr(pygame, "mixer"):
                        try:
                            if not pygame.mixer.get_init():
                                pygame.mixer.init(frequency=24000, size=-16, channels=2, buffer=2048)
                            self._mixer_initialized = True
                            logger.info("Pygame mixer initialized successfully.")
                            return
                        except Exception:
                            pass
        except Exception as e:
            logger.debug(f"Pygame mixer initialization skipped: {e}")

        self._mixer_initialized = False
        logger.info("Using system audio player for playback (mpv / ffplay).")

    def _init_speech_recognizer(self) -> None:
        """Initialize SpeechRecognition recognizer and microphone with snappy pause thresholds."""
        try:
            import speech_recognition as sr
            self._recognizer = sr.Recognizer()
            self._recognizer.energy_threshold = 300
            self._recognizer.dynamic_energy_threshold = True
            # Fast, snappy pause thresholds so speech ends are detected promptly without lag
            self._recognizer.pause_threshold = 0.8
            self._recognizer.non_speaking_duration = 0.4
            self._recognizer.phrase_threshold = 0.2

            try:
                with self._suppress_c_stderr():
                    self._microphone = sr.Microphone()
                self._stt_available = True
                logger.info("Speech recognition microphone detected successfully.")
            except Exception as mic_err:
                logger.warning(f"Microphone input device unavailable ({mic_err}). Text mode remains fully functional.")
                self._microphone = None
                self._stt_available = False
        except ImportError:
            logger.warning("speech_recognition library is not available.")
            self._recognizer = None
            self._stt_available = False

    @property
    def is_stt_ready(self) -> bool:
        """Check if microphone and STT are operational."""
        return self._stt_available and self._recognizer is not None and self._microphone is not None

    @property
    def is_tts_ready(self) -> bool:
        """Check if TTS playback is available."""
        return True

    def stop_speaking(self) -> None:
        """Immediately terminate any running audio playback process."""
        self._stop_event.set()
        if self._current_player_proc:
            try:
                if self._current_player_proc.poll() is None:
                    self._current_player_proc.terminate()
                    self._current_player_proc.wait(timeout=0.3)
            except Exception:
                try:
                    self._current_player_proc.kill()
                except Exception:
                    pass
            self._current_player_proc = None

        if self._mixer_initialized:
            try:
                import pygame
                if hasattr(pygame, "mixer") and pygame.mixer.get_init():
                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
            except Exception:
                pass

    def is_speaking(self) -> bool:
        """Check whether audio is currently playing."""
        if self._current_player_proc and self._current_player_proc.poll() is None:
            return True
        if self._mixer_initialized:
            try:
                import pygame
                if hasattr(pygame, "mixer") and pygame.mixer.get_init():
                    return pygame.mixer.music.get_busy()
            except Exception:
                pass
        return False

    async def _generate_audio_file(self, text: str, output_path: str) -> bool:
        """Synthesize Bengali speech using ElevenLabs (with fallback to edge-tts)."""
        clean_text = self._sanitize_text_for_speech(text)
        if not clean_text:
            return False

        # Attempt 1: ElevenLabs AI Voice (Ultra-Realistic Girl Voice)
        if self.settings.tts_provider == "elevenlabs" and self.settings.elevenlabs_api_key:
            try:
                import httpx
                voice_id = self.settings.elevenlabs_voice_id or "EXAVITQu4vr4xnSDxMaL"
                model_id = self.settings.elevenlabs_model_id or "eleven_multilingual_v2"
                url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
                headers = {
                    "xi-api-key": self.settings.elevenlabs_api_key,
                    "Content-Type": "application/json",
                }
                payload = {
                    "text": clean_text,
                    "model_id": model_id,
                    "voice_settings": {
                        "stability": 0.5,
                        "similarity_boost": 0.8,
                    }
                }
                async with httpx.AsyncClient(timeout=15.0) as client:
                    resp = await client.post(url, headers=headers, json=payload)
                    if resp.status_code == 200 and len(resp.content) > 100:
                        with open(output_path, "wb") as f:
                            f.write(resp.content)
                        return True
                    else:
                        logger.warning(f"ElevenLabs TTS response status {resp.status_code}. Falling back to edge-tts.")
            except Exception as e:
                logger.warning(f"ElevenLabs TTS failed: {e}. Falling back to edge-tts.")

        # Attempt 2: Microsoft edge-tts (Fast, reliable, unlimited)
        try:
            import edge_tts
            rate = self.settings.voice_rate if re.match(r"^[+-]\d+%$", str(self.settings.voice_rate)) else "+0%"
            volume = self.settings.voice_volume if re.match(r"^[+-]\d+%$", str(self.settings.voice_volume)) else "+0%"

            communicate = edge_tts.Communicate(
                text=clean_text,
                voice=self.settings.voice_name,
                rate=rate,
                volume=volume,
            )
            await communicate.save(output_path)
            return True
        except Exception as e:
            logger.error(f"edge-tts failed: {e}")
            return False

    def _sanitize_text_for_speech(self, text: str) -> str:
        """Clean markdown symbols, code blocks, emojis, and noisy formatting for natural Bangladeshi speech."""
        if not text:
            return ""

        # 1. Replace code blocks
        clean = re.sub(r"```[\s\S]*?```", "কোড ব্লকের বিস্তারিত টার্মিনালে প্রদর্শিত হয়েছে।", text)
        clean = re.sub(r"`([^`]+)`", r"\1", clean)
        clean = re.sub(r"\[([^\]]+)\]\([^\)]+\)", r"\1", clean)

        # 2. Phonetic Bengali pronunciation for common technical terms for authentic local accent
        phonetic_replacements = [
            (r"\bVS\s*Code\b", "ভিএস কোড"),
            (r"\bVisual\s+Studio\s+Code\b", "ভিজুয়াল স্টুডিও কোড"),
            (r"\bTerminal\b", "টার্মিনাল"),
            (r"\bKonsole\b", "কনসোল"),
            (r"\bTelegram\b", "টেলিগ্রাম"),
            (r"\bChrome\b", "ক্রোম"),
            (r"\bFirefox\b", "ফায়ারফক্স"),
            (r"\bBrowser\b", "ব্রাউজার"),
            (r"\bPython\b", "পাইথন"),
            (r"\bRAM\b", "র‍্যাম"),
            (r"\bCPU\b", "সিপিইউ"),
            (r"\bGPU\b", "জিপিইউ"),
            (r"\bIDE\b", "আইডিই"),
            (r"\bGit\b", "গিট"),
            (r"\bGitHub\b", "গিটহাব"),
            (r"\bDesktop\b", "ডেস্কটপ"),
            (r"\bJARVIS\b", "জার্ভিস"),
            (r"\bmonaAi\b", "মোনা এআই"),
            (r"\bOK\b", "ঠিক আছে"),
            (r"\bHi\b", "হাই"),
            (r"\bHello\b", "হ্যালো"),
            (r"\bError\b", "এরর"),
            (r"\bScreenshot\b", "স্ক্রিনশট"),
            (r"\bWindow\b", "উইন্ডো"),
            (r"\bFile\b", "ফাইল"),
            (r"\bFolder\b", "ফোল্ডার"),
        ]
        for pattern, replacement in phonetic_replacements:
            clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)

        # 3. Clean list bullets and numbering into natural pause commas
        clean = re.sub(r"^\s*[\*\-•]\s*", ", ", clean, flags=re.MULTILINE)
        clean = re.sub(r"^\s*\d+\.\s*", ", ", clean, flags=re.MULTILINE)
        clean = re.sub(r"(?:,\s*)+\d+\.\s*", ", ", clean)

        # 4. Remove all emojis (emojis disrupt neural TTS prosody)
        emoji_pattern = re.compile(
            "["
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U00002702-\U000027B0"
            "\U000024C2-\U0001F251"
            "\U0001F900-\U0001F9FF"  # supplemental symbols
            "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-A
            "\U00002600-\U000026FF"  # misc symbols
            "]+",
            flags=re.UNICODE,
        )
        clean = emoji_pattern.sub(" ", clean)

        # 5. Remove leftover markdown characters
        clean = re.sub(r"[\*#_~>|]", " ", clean)

        # 6. Normalize whitespace and trailing punctuation
        clean = re.sub(r"\s+", " ", clean).strip()
        # Clean double commas or awkward punctuation
        clean = re.sub(r",\s*,+", ",", clean)
        clean = re.sub(r"^[,\s]+", "", clean)

        return clean

    def speak(self, text: str, blocking: bool = True) -> None:
        """Synthesize and play speech in natural Bengali with strict serial locking to prevent double voice."""
        with self._playback_lock:
            self.stop_speaking()
            self._stop_event.clear()

            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                    temp_file = f.name

                asyncio.run(self._generate_audio_file(text, temp_file))

                if not os.path.exists(temp_file) or os.path.getsize(temp_file) == 0:
                    return

                # Option 1: pygame.mixer if available
                if self._mixer_initialized:
                    import pygame
                    pygame.mixer.music.load(temp_file)
                    pygame.mixer.music.play()

                    while pygame.mixer.music.get_busy() and not self._stop_event.is_set():
                        time.sleep(0.08)

                    pygame.mixer.music.stop()
                    pygame.mixer.music.unload()
                else:
                    # Option 2: System audio player (mpv / ffplay)
                    player_bin = shutil.which("mpv") or shutil.which("ffplay")
                    if player_bin:
                        cmd = (
                            [player_bin, "--no-video", "--really-quiet", temp_file]
                            if "mpv" in player_bin
                            else [player_bin, "-nodisp", "-autoexit", "-loglevel", "quiet", temp_file]
                        )
                        self._current_player_proc = subprocess.Popen(
                            cmd,
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL,
                        )
                        while self._current_player_proc.poll() is None and not self._stop_event.is_set():
                            time.sleep(0.08)

                        if self._stop_event.is_set() and self._current_player_proc.poll() is None:
                            self._current_player_proc.terminate()

                # Brief settling pause to prevent microphone from picking up lingering sound
                time.sleep(0.10)

            except Exception as e:
                logger.error(f"Voice playback exception: {e}")
            finally:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except OSError:
                        pass

    def listen(self, timeout: int = 10, phrase_time_limit: int = 35) -> Optional[str]:
        """Listen from microphone and transcribe using Bengali locale (bn-BD).

        Supports slow, relaxed speech with natural pauses without cutting off mid-sentence.

        Args:
            timeout: Max seconds to wait for speech start.
            phrase_time_limit: Max duration of voice phrase.

        Returns:
            Transcribed text in Bengali, or None if no speech detected.
        """
        if not self.is_stt_ready:
            logger.warning("Microphone/STT is not operational.")
            return None

        import speech_recognition as sr

        try:
            with self._microphone as source:
                logger.debug("Listening for Bengali speech...")
                audio = self._recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )

            logger.debug("Transcribing audio via Google Speech (bn-BD)...")
            text = self._recognizer.recognize_google(audio, language=self.settings.voice_locale)
            return text.strip() if text else None

        except sr.WaitTimeoutError:
            logger.debug("Listening timed out with no speech detected.")
            return None
        except sr.UnknownValueError:
            logger.debug("Google Speech Recognition could not understand audio.")
            return None
        except sr.RequestError as e:
            logger.error(f"Speech recognition service request error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error during audio capture or transcription: {e}")
            return None

    def shutdown(self) -> None:
        """Gracefully release audio subsystem."""
        self.stop_speaking()
        if self._mixer_initialized:
            try:
                import pygame
                if hasattr(pygame, "mixer") and pygame.mixer.get_init():
                    pygame.mixer.quit()
            except Exception:
                pass


_voice_engine_instance: Optional[BengaliVoiceEngine] = None


def get_voice_engine() -> BengaliVoiceEngine:
    """Get or create singleton BengaliVoiceEngine."""
    global _voice_engine_instance
    if _voice_engine_instance is None:
        _voice_engine_instance = BengaliVoiceEngine()
    return _voice_engine_instance
