"""Voice interface handling Speech-to-Text (STT) and Text-to-Speech (TTS)."""
import logging
import threading
from typing import Optional

from config.settings import get_settings

logger = logging.getLogger(__name__)


class VoiceInterface:
    """Provides speech recognition and speech synthesis with graceful hardware fallbacks."""

    def __init__(self):
        self.settings = get_settings()
        self.recognizer = None
        self.microphone = None
        self.tts_engine = None
        self._tts_lock = threading.Lock()

        self._init_stt()
        self._init_tts()

    def _init_stt(self) -> None:
        """Initialize SpeechRecognition recognizer and microphone."""
        try:
            import speech_recognition as sr
            self.recognizer = sr.Recognizer()
            self.recognizer.energy_threshold = 300
            self.recognizer.dynamic_energy_threshold = True

            # Attempt to probe default microphone
            try:
                self.microphone = sr.Microphone()
                with self.microphone as source:
                    self.recognizer.adjust_for_ambient_noise(source, duration=0.5)
                logger.info("Voice STT microphone initialized successfully.")
            except Exception as mic_err:
                logger.warning(
                    f"Microphone could not be initialized (PyAudio or audio device issue): {mic_err}. "
                    "Voice input will be disabled."
                )
                self.microphone = None

        except ImportError:
            logger.warning(
                "SpeechRecognition package is not installed. Install with 'pip install SpeechRecognition'."
            )
            self.recognizer = None

    def _init_tts(self) -> None:
        """Initialize authentic Bangladeshi Bengali Neural Voice Engine."""
        try:
            import importlib.util
            from pathlib import Path
            engine_path = Path(__file__).resolve().parent.parent / "jarvis-core" / "interfaces" / "voice_engine.py"
            spec = importlib.util.spec_from_file_location("jarvis_voice_engine", str(engine_path))
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
            self._bengali_engine = mod.get_voice_engine()
            self.tts_engine = self._bengali_engine
            logger.info("Bangladeshi Bengali Neural Voice Engine initialized successfully.")
        except Exception as e:
            logger.warning(f"Bengali Voice Engine initialization fallback: {e}")
            self._bengali_engine = None
            try:
                import pyttsx3
                self.tts_engine = pyttsx3.init()
            except Exception:
                self.tts_engine = None

    def is_stt_available(self) -> bool:
        """Check if Speech-to-Text is available."""
        return self.recognizer is not None and self.microphone is not None

    def is_tts_available(self) -> bool:
        """Check if Text-to-Speech is available."""
        return self.tts_engine is not None

    def listen(self, timeout: int = 6, phrase_time_limit: int = 15) -> Optional[str]:
        """Listen for user voice command via microphone and convert to text.

        Args:
            timeout: Max seconds to wait for speech to start.
            phrase_time_limit: Max duration of speech phrase.

        Returns:
            Transcribed text, or None if no speech or error.
        """
        if not self.is_stt_available():
            logger.warning("Voice listening attempted but STT/Microphone is unavailable.")
            return None

        import speech_recognition as sr

        try:
            with self.microphone as source:
                logger.debug("Listening for voice input...")
                audio = self.recognizer.listen(
                    source,
                    timeout=timeout,
                    phrase_time_limit=phrase_time_limit,
                )

            logger.debug("Processing speech transcription...")
            # Use Google Speech Recognition
            text = self.recognizer.recognize_google(
                audio,
                language=self.settings.voice_language,
            )
            return text.strip()

        except sr.WaitTimeoutError:
            logger.debug("Voice listening timed out (silence).")
            return None
        except sr.UnknownValueError:
            logger.debug("Speech was unintelligible.")
            return None
        except sr.RequestError as e:
            logger.error(f"Could not request results from STT service: {e}")
            return None
        except Exception as e:
            logger.error(f"Voice listening error: {e}")
            return None

    def speak(self, text: str) -> None:
        """Synthesize and vocalize text.

        Args:
            text: Text to speak out loud.
        """
        if not text or not text.strip():
            return

        clean_text = text.strip()

        if not self.is_tts_available():
            # Fallback: print to console
            print(f"[Voice TTS]: {clean_text}")
            return

        if self._bengali_engine:
            self._bengali_engine.speak(clean_text, blocking=True)
            return

        with self._tts_lock:
            try:
                if hasattr(self.tts_engine, "say"):
                    self.tts_engine.say(clean_text)
                    self.tts_engine.runAndWait()
                else:
                    print(f"[Voice TTS]: {clean_text}")
            except Exception as e:
                logger.error(f"TTS output error: {e}")
                print(f"[Voice TTS]: {clean_text}")
