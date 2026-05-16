"""Provider adapters for external APIs.

Currently just wrappers around Sarvam (TTS + translate) and the Gemini
LLM client. Music generation was removed in the LTX-2 migration —
non-speaker scenes now use LTX-2's native audio output, speaker scenes
use TTS + lip-sync.
"""
