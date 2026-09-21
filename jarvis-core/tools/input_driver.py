"""Native Linux Virtual Input Driver for JARVIS.

Provides direct kernel-level keyboard and mouse simulation via /dev/uinput (evdev).
Works seamlessly on Linux Wayland (KDE Plasma, GNOME, Hyprland) and X11 without root
or third-party tools like xdotool/ydotool.
"""
import logging
import os
import subprocess
import time
from typing import List, Optional, Union

logger = logging.getLogger(__name__)

# Try loading evdev
try:
    import evdev
    from evdev import UInput, ecodes as e
    EVDEV_AVAILABLE = True
except ImportError:
    evdev = None
    e = None
    UInput = None
    EVDEV_AVAILABLE = False


def set_system_clipboard(text: str) -> bool:
    """Set system clipboard contents reliably across KDE Plasma, Wayland, and X11."""
    # 1. Try KDE Plasma qdbus6
    try:
        res = subprocess.run(
            ["qdbus6", "org.kde.klipper", "/klipper", "org.kde.klipper.klipper.setClipboardContents", text],
            capture_output=True,
            timeout=2,
        )
        if res.returncode == 0:
            return True
    except Exception:
        pass

    # 2. Try wl-copy (Wayland clipboard)
    try:
        p = subprocess.Popen(["wl-copy"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=2)
        if p.returncode == 0:
            return True
    except Exception:
        pass

    # 3. Try xclip (X11 clipboard)
    try:
        p = subprocess.Popen(["xclip", "-selection", "clipboard"], stdin=subprocess.PIPE)
        p.communicate(input=text.encode("utf-8"), timeout=2)
        if p.returncode == 0:
            return True
    except Exception:
        pass

    # 4. Try pyperclip fallback
    try:
        import pyperclip
        pyperclip.copy(text)
        return True
    except Exception:
        pass

    return False


# Build comprehensive keycode mapping if evdev is present
_KEY_MAP = {}
_SHIFT_MAP = {}

if EVDEV_AVAILABLE:
    _KEY_MAP = {
        # Alphanumeric
        "a": e.KEY_A, "b": e.KEY_B, "c": e.KEY_C, "d": e.KEY_D, "e": e.KEY_E,
        "f": e.KEY_F, "g": e.KEY_G, "h": e.KEY_H, "i": e.KEY_I, "j": e.KEY_J,
        "k": e.KEY_K, "l": e.KEY_L, "m": e.KEY_M, "n": e.KEY_N, "o": e.KEY_O,
        "p": e.KEY_P, "q": e.KEY_Q, "r": e.KEY_R, "s": e.KEY_S, "t": e.KEY_T,
        "u": e.KEY_U, "v": e.KEY_V, "w": e.KEY_W, "x": e.KEY_X, "y": e.KEY_Y,
        "z": e.KEY_Z,
        "0": e.KEY_0, "1": e.KEY_1, "2": e.KEY_2, "3": e.KEY_3, "4": e.KEY_4,
        "5": e.KEY_5, "6": e.KEY_6, "7": e.KEY_7, "8": e.KEY_8, "9": e.KEY_9,

        # Editing & Navigation
        "enter": e.KEY_ENTER, "return": e.KEY_ENTER, "\n": e.KEY_ENTER,
        "esc": e.KEY_ESC, "escape": e.KEY_ESC,
        "backspace": e.KEY_BACKSPACE, "tab": e.KEY_TAB, "\t": e.KEY_TAB,
        "space": e.KEY_SPACE, " ": e.KEY_SPACE,
        "delete": e.KEY_DELETE, "del": e.KEY_DELETE,
        "insert": e.KEY_INSERT,
        "home": e.KEY_HOME, "end": e.KEY_END,
        "pageup": e.KEY_PAGEUP, "pagedown": e.KEY_PAGEDOWN,
        "up": e.KEY_UP, "down": e.KEY_DOWN, "left": e.KEY_LEFT, "right": e.KEY_RIGHT,

        # Modifiers
        "ctrl": e.KEY_LEFTCTRL, "leftctrl": e.KEY_LEFTCTRL, "control": e.KEY_LEFTCTRL,
        "rightctrl": e.KEY_RIGHTCTRL,
        "shift": e.KEY_LEFTSHIFT, "leftshift": e.KEY_LEFTSHIFT,
        "rightshift": e.KEY_RIGHTSHIFT,
        "alt": e.KEY_LEFTALT, "leftalt": e.KEY_LEFTALT,
        "rightalt": e.KEY_RIGHTALT,
        "meta": e.KEY_LEFTMETA, "super": e.KEY_LEFTMETA, "win": e.KEY_LEFTMETA,
        "capslock": e.KEY_CAPSLOCK,

        # Function Keys
        "f1": e.KEY_F1, "f2": e.KEY_F2, "f3": e.KEY_F3, "f4": e.KEY_F4,
        "f5": e.KEY_F5, "f6": e.KEY_F6, "f7": e.KEY_F7, "f8": e.KEY_F8,
        "f9": e.KEY_F9, "f10": e.KEY_F10, "f11": e.KEY_F11, "f12": e.KEY_F12,

        # Punctuation
        "-": e.KEY_MINUS, "=": e.KEY_EQUAL,
        "[": e.KEY_LEFTBRACE, "]": e.KEY_RIGHTBRACE,
        "\\": e.KEY_BACKSLASH, ";": e.KEY_SEMICOLON,
        "'": e.KEY_APOSTROPHE, "`": e.KEY_GRAVE,
        ",": e.KEY_COMMA, ".": e.KEY_DOT, "/": e.KEY_SLASH,
    }

    _SHIFT_MAP = {
        "!": (e.KEY_1, True), "@": (e.KEY_2, True), "#": (e.KEY_3, True),
        "$": (e.KEY_4, True), "%": (e.KEY_5, True), "^": (e.KEY_6, True),
        "&": (e.KEY_7, True), "*": (e.KEY_8, True), "(": (e.KEY_9, True),
        ")": (e.KEY_0, True), "_": (e.KEY_MINUS, True), "+": (e.KEY_EQUAL, True),
        "{": (e.KEY_LEFTBRACE, True), "}": (e.KEY_RIGHTBRACE, True),
        "|": (e.KEY_BACKSLASH, True), ":": (e.KEY_SEMICOLON, True),
        "\"": (e.KEY_APOSTROPHE, True), "~": (e.KEY_GRAVE, True),
        "<": (e.KEY_COMMA, True), ">": (e.KEY_DOT, True), "?": (e.KEY_SLASH, True),
    }


class JarvisVirtualInput:
    """Singleton virtual input controller wrapping Linux kernel uinput subsystem."""

    _instance: Optional["JarvisVirtualInput"] = None

    def __init__(self):
        self._uinput: Optional[UInput] = None
        self._initialized = False
        self._setup_uinput()

    @classmethod
    def get_instance(cls) -> "JarvisVirtualInput":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _setup_uinput(self):
        if not EVDEV_AVAILABLE:
            logger.warning("evdev not available; will use pyautogui fallback.")
            return

        try:
            # Build all supported capabilities
            all_keys = list(set(_KEY_MAP.values()))
            for key, _ in _SHIFT_MAP.values():
                if key not in all_keys:
                    all_keys.append(key)

            mouse_buttons = [e.BTN_LEFT, e.BTN_RIGHT, e.BTN_MIDDLE]
            cap = {
                e.EV_KEY: all_keys + mouse_buttons,
                e.EV_REL: [e.REL_X, e.REL_Y, e.REL_WHEEL],
            }

            self._uinput = UInput(cap, name="JARVIS-Hardware-Controller")
            self._initialized = True
            logger.info("JARVIS Virtual Input Driver successfully initialized via /dev/uinput!")
        except Exception as err:
            logger.warning(f"Could not open /dev/uinput ({err}). PyAutoGUI fallback will be used.")
            self._uinput = None
            self._initialized = False

    def is_active(self) -> bool:
        return self._initialized and self._uinput is not None

    def key_down(self, key_name: str) -> bool:
        """Hold a key down."""
        if not self.is_active():
            return False
        clean = key_name.lower().strip()
        code = _KEY_MAP.get(clean)
        if code:
            self._uinput.write(e.EV_KEY, code, 1)
            self._uinput.syn()
            return True
        return False

    def key_up(self, key_name: str) -> bool:
        """Release a key."""
        if not self.is_active():
            return False
        clean = key_name.lower().strip()
        code = _KEY_MAP.get(clean)
        if code:
            self._uinput.write(e.EV_KEY, code, 0)
            self._uinput.syn()
            return True
        return False

    def press_key(self, key_name: str, delay: float = 0.04) -> bool:
        """Press and release a single key."""
        clean = key_name.lower().strip()

        if self.is_active():
            # Check shifted symbol
            if clean in _SHIFT_MAP:
                code, need_shift = _SHIFT_MAP[clean]
                self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                self._uinput.syn()
                time.sleep(0.01)
                self._uinput.write(e.EV_KEY, code, 1)
                self._uinput.syn()
                time.sleep(delay)
                self._uinput.write(e.EV_KEY, code, 0)
                self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                self._uinput.syn()
                return True

            code = _KEY_MAP.get(clean)
            if code:
                self._uinput.write(e.EV_KEY, code, 1)
                self._uinput.syn()
                time.sleep(delay)
                self._uinput.write(e.EV_KEY, code, 0)
                self._uinput.syn()
                return True

        # Fallback to PyAutoGUI
        try:
            import sys
            sys.modules["mouseinfo"] = None
            import pyautogui
            pyautogui.press(key_name)
            return True
        except Exception as ex:
            logger.error(f"Failed to press key '{key_name}': {ex}")
            return False

    def hotkey(self, *keys: str, delay: float = 0.05) -> bool:
        """Trigger a combination of keys (e.g. ['ctrl', 'f'], ['ctrl', 'v'], ['alt', 'f4'])."""
        if self.is_active():
            codes = [_KEY_MAP.get(k.lower().strip()) for k in keys]
            if all(c is not None for c in codes):
                for c in codes:
                    self._uinput.write(e.EV_KEY, c, 1)
                    self._uinput.syn()
                    time.sleep(0.02)
                time.sleep(delay)
                for c in reversed(codes):
                    self._uinput.write(e.EV_KEY, c, 0)
                    self._uinput.syn()
                    time.sleep(0.02)
                return True

        # Fallback to PyAutoGUI
        try:
            import sys
            sys.modules["mouseinfo"] = None
            import pyautogui
            pyautogui.hotkey(*keys)
            return True
        except Exception as ex:
            logger.error(f"Failed hotkey {keys}: {ex}")
            return False

    def type_text(self, text: str, interval: float = 0.02) -> bool:
        """Type arbitrary text. For non-ASCII (Bangla, emojis) or long strings, pastes via clipboard."""
        # Unicode (Bangla/Emojis) or multiline text: paste via clipboard
        if any(ord(c) > 127 for c in text) or "\n" in text or len(text) > 40:
            return self.paste_text(text)

        if self.is_active():
            success = True
            for char in text:
                low = char.lower()
                is_upper = char.isupper()

                if char in _SHIFT_MAP:
                    code, _ = _SHIFT_MAP[char]
                    self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                    self._uinput.syn()
                    self._uinput.write(e.EV_KEY, code, 1)
                    self._uinput.syn()
                    time.sleep(interval)
                    self._uinput.write(e.EV_KEY, code, 0)
                    self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                    self._uinput.syn()
                elif low in _KEY_MAP:
                    code = _KEY_MAP[low]
                    if is_upper:
                        self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 1)
                        self._uinput.syn()
                    self._uinput.write(e.EV_KEY, code, 1)
                    self._uinput.syn()
                    time.sleep(interval)
                    self._uinput.write(e.EV_KEY, code, 0)
                    if is_upper:
                        self._uinput.write(e.EV_KEY, e.KEY_LEFTSHIFT, 0)
                    self._uinput.syn()
                else:
                    success = False
                    break
            if success:
                return True

        # Fallback paste
        return self.paste_text(text)

    def paste_text(self, text: str) -> bool:
        """Copy text to clipboard and trigger Ctrl+V paste."""
        set_system_clipboard(text)
        time.sleep(0.08)
        return self.hotkey("ctrl", "v")

    def mouse_click(self, button: str = "left", delay: float = 0.04) -> bool:
        """Click a mouse button ('left', 'right', 'middle')."""
        button_map = {
            "left": e.BTN_LEFT if EVDEV_AVAILABLE else None,
            "right": e.BTN_RIGHT if EVDEV_AVAILABLE else None,
            "middle": e.BTN_MIDDLE if EVDEV_AVAILABLE else None,
        }

        if self.is_active():
            btn_code = button_map.get(button.lower().strip(), e.BTN_LEFT)
            if btn_code:
                self._uinput.write(e.EV_KEY, btn_code, 1)
                self._uinput.syn()
                time.sleep(delay)
                self._uinput.write(e.EV_KEY, btn_code, 0)
                self._uinput.syn()
                return True

        # Fallback
        try:
            import sys
            sys.modules["mouseinfo"] = None
            import pyautogui
            pyautogui.click(button=button)
            return True
        except Exception as ex:
            logger.error(f"Mouse click failed: {ex}")
            return False

    def mouse_move(self, dx: int, dy: int) -> bool:
        """Move mouse pointer relatively."""
        if self.is_active():
            self._uinput.write(e.EV_REL, e.REL_X, int(dx))
            self._uinput.write(e.EV_REL, e.REL_Y, int(dy))
            self._uinput.syn()
            return True
        try:
            import sys
            sys.modules["mouseinfo"] = None
            import pyautogui
            pyautogui.moveRel(dx, dy)
            return True
        except Exception:
            return False

    def mouse_scroll(self, clicks: int) -> bool:
        """Scroll mouse wheel."""
        if self.is_active():
            self._uinput.write(e.EV_REL, e.REL_WHEEL, int(clicks))
            self._uinput.syn()
            return True
        try:
            import sys
            sys.modules["mouseinfo"] = None
            import pyautogui
            pyautogui.scroll(clicks)
            return True
        except Exception:
            return False

    def close(self):
        """Cleanly close uinput device handle."""
        if self._uinput:
            try:
                self._uinput.close()
            except Exception:
                pass
            self._uinput = None
            self._initialized = False


def get_virtual_input() -> JarvisVirtualInput:
    """Get the active JarvisVirtualInput singleton instance."""
    return JarvisVirtualInput.get_instance()
