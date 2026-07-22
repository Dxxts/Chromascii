import numpy as np
from PIL import Image


def cellgrid_to_image(rgb, cols, rows, out_w, out_h):
    bw = max(1, -(-out_w // cols))
    bh = max(1, -(-out_h // rows))
    small = np.array(Image.fromarray(rgb).resize((cols, rows), Image.NEAREST))
    up = small.repeat(bh, axis=0).repeat(bw, axis=1)
    out = up[:out_h, :out_w].copy()
    out[::bh] = (out[::bh].astype('float32') * 0.30).astype('uint8')
    out[:, ::bw] = (out[:, ::bw].astype('float32') * 0.30).astype('uint8')
    return out.astype('uint8')


class Exporter:
    def __init__(self, out_path, fps, size):
        import cv2
        w, h = size
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        self._writer = cv2.VideoWriter(out_path, fourcc, max(fps, 1.0), (w, h))
        if not self._writer.isOpened():
            raise RuntimeError(f'Cannot open export target: {out_path}')

    def write(self, rgb_frame):
        bgr = rgb_frame[:, :, ::-1]
        self._writer.write(bgr)

    def close(self):
        self._writer.release()
