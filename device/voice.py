"""
voice.py — microphone recording and speaker playback for M5Stack Core2.

Hardware:
  Microphone: SPM1423 PDM mic (CLK=GPIO0, DATA=GPIO34)
  Speaker:    AW88298 I2S amplifier

The /voice_raw middleware endpoint expects a complete WAV file in request.data
and returns a WAV file directly. This module handles:
  - Building the 44-byte WAV header around raw PCM samples
  - Recording from the built-in mic
  - Playing back WAV bytes through the built-in speaker

UIFlow note: If your UIFlow version exposes `mic` and `speaker` as global
objects (after `from m5stack import *`), use those instead of the I2S
approach below. The I2S approach is the lower-level fallback.

To test without hardware, record_wav() can return a short silent WAV by
setting MOCK_AUDIO = True below.
"""
import ustruct
import utime

# Set True to return a silent WAV instead of recording (useful for UI testing)
MOCK_AUDIO = False

SAMPLE_RATE  = 8000   # Hz — matches what Whisper handles well at low bandwidth
BITS         = 16
CHANNELS     = 1
TEMP_WAV     = "/flash/tmp_response.wav"


# ── WAV header ────────────────────────────────────────────────────────────────

def _make_wav_header(num_samples):
    """Return a 44-byte standard PCM WAV header."""
    data_size = num_samples * CHANNELS * (BITS // 8)
    h = bytearray(44)
    h[0:4]  = b"RIFF"
    ustruct.pack_into("<I", h, 4,  36 + data_size)
    h[8:12]  = b"WAVE"
    h[12:16] = b"fmt "
    ustruct.pack_into("<I", h, 16, 16)                            # sub-chunk size
    ustruct.pack_into("<H", h, 20, 1)                             # PCM format
    ustruct.pack_into("<H", h, 22, CHANNELS)
    ustruct.pack_into("<I", h, 24, SAMPLE_RATE)
    ustruct.pack_into("<I", h, 28, SAMPLE_RATE * CHANNELS * BITS // 8)  # byte rate
    ustruct.pack_into("<H", h, 32, CHANNELS * BITS // 8)          # block align
    ustruct.pack_into("<H", h, 34, BITS)
    h[36:40] = b"data"
    ustruct.pack_into("<I", h, 40, data_size)
    return bytes(h)


def _silent_wav(duration_ms):
    num_samples = SAMPLE_RATE * duration_ms // 1000
    return _make_wav_header(num_samples) + bytes(num_samples * CHANNELS * (BITS // 8))


# ── Recording ─────────────────────────────────────────────────────────────────

def record_wav(duration_ms=5000):
    """
    Record audio from the built-in SPM1423 PDM microphone.
    Returns complete WAV bytes (header + PCM) or None on failure.

    Tries UIFlow's global `mic` object first (simpler).
    Falls back to direct I2S if not available.

    If MOCK_AUDIO is True, returns a silent WAV (for UI-only testing).
    """
    if MOCK_AUDIO:
        return _silent_wav(duration_ms)

    num_samples = SAMPLE_RATE * duration_ms // 1000

    # ── UIFlow mic API (try first) ────────────────────────────────────────────
    try:
        from m5stack import mic  # available in UIFlow after 'from m5stack import *'
        mic.begin(sample_rate=SAMPLE_RATE, bit_count=BITS)
        raw = mic.record(num_samples)
        mic.end()
        header = _make_wav_header(num_samples)
        return header + bytes(raw)
    except Exception:
        pass

    # ── Direct I2S fallback (standard MicroPython) ────────────────────────────
    try:
        from machine import I2S, Pin
        import uarray

        audio_in = I2S(
            0,
            sck=Pin(0),    # SPM1423 CLK
            ws=Pin(0),     # PDM — same pin as CLK
            sd=Pin(34),    # SPM1423 DATA
            mode=I2S.RX,
            bits=BITS,
            format=I2S.MONO,
            rate=SAMPLE_RATE,
            ibuf=num_samples * 2 + 256,
        )
        buf = uarray.array("h", [0] * num_samples)
        audio_in.readinto(buf)
        audio_in.deinit()
        header = _make_wav_header(num_samples)
        return header + bytes(buf)
    except Exception as e:
        print("voice: record_wav error —", e)
        return None


# ── Playback ──────────────────────────────────────────────────────────────────

def play_wav(wav_bytes):
    """
    Play WAV bytes through the built-in speaker.

    Writes to a temp file in flash then uses UIFlow's speaker.playWAV().
    Direct in-memory playback API varies by UIFlow version; flash file
    is the most portable approach.
    """
    if not wav_bytes:
        return

    # Write response to flash
    try:
        with open(TEMP_WAV, "wb") as f:
            f.write(wav_bytes)
    except Exception as e:
        print("voice: play_wav write error —", e)
        return

    # Play via UIFlow speaker
    try:
        from m5stack import speaker
        speaker.setVolume(6)
        speaker.playWAV(TEMP_WAV, SAMPLE_RATE)
        # Approximate wait: give speaker time to finish
        # (UIFlow playWAV may be async on some firmware versions)
        play_ms = (len(wav_bytes) - 44) * 1000 // (SAMPLE_RATE * CHANNELS * BITS // 8)
        utime.sleep_ms(max(play_ms, 500))
    except Exception as e:
        print("voice: play_wav speaker error —", e)
