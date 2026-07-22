import time
from pathlib import Path

_ASSETS = Path(__file__).resolve().parent.parent / 'assets'


def play_chime(name='plink', wait=True):
    from ..renderer.audio import AudioPlayer, AUDIO_AVAILABLE

    if not AUDIO_AVAILABLE:
        return
    asset = _ASSETS / f'{name}.mp3'
    if not asset.is_file():
        return

    player = AudioPlayer(str(asset))
    if not player.start():
        return
    if wait:
        time.sleep(0.55)
        player.stop()
