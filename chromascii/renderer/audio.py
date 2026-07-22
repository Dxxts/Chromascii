import collections
import threading

import numpy as np

try:
    import av
    import sounddevice as sd
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False


class AudioPlayer:
    def __init__(self, path):
        self.path = path
        self._container = None
        self._astream = None
        self._resampler = None
        self._stream = None
        self._decode_thread = None
        self._stop_ev = threading.Event()
        self._playing = False
        self._samplerate = 48000
        self._out_channels = 2
        self._frames_written = 0
        self._buf_lock = threading.Lock()
        self._buffer = collections.deque()

    def start(self, start_pos=0.0):
        if not AUDIO_AVAILABLE:
            return False
        try:
            self._container = av.open(self.path)
            self._astream = next((s for s in self._container.streams if s.type == 'audio'), None)
            if self._astream is None:
                return False
            self._samplerate = self._astream.codec_context.sample_rate or 48000
            src_channels = self._astream.codec_context.channels or 2
            self._out_channels = 2 if src_channels >= 2 else 1
            layout = 'stereo' if self._out_channels == 2 else 'mono'
            self._resampler = av.AudioResampler(format='fltp', layout=layout, rate=self._samplerate)
            if start_pos > 0:
                self._container.seek(int(start_pos * av.time_base), any_frame=False)
        except Exception:
            self._close_container()
            return False

        try:
            self._stream = sd.OutputStream(
                samplerate=self._samplerate,
                channels=self._out_channels,
                dtype='float32',
                callback=self._callback,
            )
            self._stream.start()
        except Exception:
            self._close_container()
            self._stream = None
            return False

        self._stop_ev.clear()
        self._playing = True
        self._frames_written = 0
        self._decode_thread = threading.Thread(target=self._decode_loop, daemon=True)
        self._decode_thread.start()
        return True

    def _decode_loop(self):
        try:
            for packet in self._container.demux(self._astream):
                if self._stop_ev.is_set():
                    break
                for frame in packet.decode():
                    resampled = self._resampler.resample(frame)
                    frames = resampled if isinstance(resampled, list) else [resampled]
                    for f in frames:
                        if f is None:
                            continue
                        arr = f.to_ndarray().astype(np.float32)
                        if arr.ndim == 2:
                            arr = arr.T
                        else:
                            arr = arr.reshape(-1, 1)
                        with self._buf_lock:
                            self._buffer.append(arr)
        except Exception:
            pass

    def _callback(self, outdata, frames, time_info, status):
        need = frames
        out_idx = 0
        with self._buf_lock:
            while need > 0 and self._buffer:
                chunk = self._buffer[0]
                take = min(need, len(chunk))
                block = chunk[:take]
                if block.shape[1] < outdata.shape[1]:
                    block = np.tile(block, (1, outdata.shape[1]))
                outdata[out_idx:out_idx + take] = block[:, :outdata.shape[1]]
                if take < len(chunk):
                    self._buffer[0] = chunk[take:]
                else:
                    self._buffer.popleft()
                out_idx += take
                need -= take
        if need > 0:
            outdata[out_idx:] = 0
        self._frames_written += frames

    def position(self):
        return self._frames_written / self._samplerate

    def is_playing(self):
        return self._playing and not self._stop_ev.is_set()

    def _close_container(self):
        if self._container:
            try:
                self._container.close()
            except Exception:
                pass
            self._container = None

    def stop(self):
        self._stop_ev.set()
        self._playing = False
        if self._stream:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None
        self._close_container()
