import glob
import logging
import os
import subprocess
import sys
import tempfile


class AudioPlayer:
    """Cross-platform audio playback for Anki vocab cards."""

    _ANKI_MEDIA_GLOB = os.path.expanduser(
        "~/Library/Application Support/Anki2/*/collection.media"
    )

    def play_bytes(self, audio_bytes: bytes) -> None:
        """Play audio from an in-memory bytes buffer."""
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_bytes)
            f.flush()
            os.fsync(f.fileno())
            tmp = f.name
        try:
            self.play_file(tmp)
        finally:
            os.unlink(tmp)

    def play_file(self, path: str) -> None:
        """Play an audio file by path."""
        if sys.platform == "darwin":
            subprocess.run(["afplay", path])
        elif sys.platform.startswith("linux"):
            if subprocess.run(["which", "paplay"], capture_output=True).returncode == 0:
                subprocess.run(["paplay", path])
            else:
                subprocess.run(["aplay", path])
        elif sys.platform == "win32":
            import winsound

            winsound.PlaySound(path, winsound.SND_FILENAME)
        else:
            logging.warning("Cannot play audio on platform %r: %s", sys.platform, path)

    def play_from_ref(self, audio_ref: str) -> None:
        """Play audio referenced by an Anki ``[sound:filename]`` tag."""
        if not audio_ref:
            return
        filename = audio_ref.removeprefix("[sound:").removesuffix("]")
        for media_dir in glob.glob(self._ANKI_MEDIA_GLOB):
            path = os.path.join(media_dir, filename)
            if os.path.exists(path):
                self.play_file(path)
                return
