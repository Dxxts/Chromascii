import numpy as np

_QUAD_CHARS = np.array(
    [' ', '▘', '▝', '▀',
     '▖', '▌', '▞', '▛',
     '▗', '▚', '▐', '▜',
     '▄', '▙', '▟', '█'],
    dtype='U1'
)


def _build_sextant_table():
    table = [None] * 64
    table[0] = ' '
    table[63] = '█'
    table[21] = '▌'
    table[42] = '▐'
    rank = 0
    for v in range(1, 63):
        if v in (21, 42):
            continue
        table[v] = chr(0x1FB00 + rank)
        rank += 1
    return np.array(table, dtype='U1')


_SEXTANT_CHARS = _build_sextant_table()

_BRAILLE_CHARS = np.array([chr(0x2800 + i) for i in range(256)], dtype='U1')
_BRAILLE_SSX = 3
_BRAILLE_SSY = 2

_OCTANT_NAMES = (
    "3,23,123,4,14,124,34,134,234,5,15,25,125,135,235,1235,45,145,245,1245,345,1345,2345,12345,"
    "6,16,26,126,36,136,236,1236,146,246,1246,346,1346,2346,12346,56,156,256,1256,356,1356,2356,12356,"
    "456,1456,2456,12456,3456,13456,23456,17,27,127,37,137,237,1237,47,147,247,1247,347,1347,2347,12347,"
    "157,257,1257,357,2357,12357,457,1457,12457,3457,13457,23457,67,167,267,1267,367,1367,2367,12367,"
    "467,1467,2467,12467,3467,13467,23467,123467,567,1567,2567,12567,3567,13567,23567,123567,"
    "4567,14567,24567,124567,34567,134567,234567,1234567,18,28,128,38,138,238,1238,48,148,248,1248,"
    "348,1348,2348,12348,58,158,258,1258,358,1358,2358,12358,458,1458,2458,12458,3458,13458,23458,123458,"
    "168,268,1268,368,2368,12368,468,1468,12468,3468,13468,23468,568,1568,2568,12568,3568,13568,23568,123568,"
    "4568,14568,24568,124568,34568,134568,234568,1234568,178,278,1278,378,1378,2378,12378,478,1478,2478,12478,"
    "3478,13478,23478,123478,578,1578,2578,12578,3578,13578,23578,123578,4578,14578,24578,124578,"
    "34578,134578,234578,1234578,678,1678,2678,12678,3678,13678,23678,123678,4678,14678,24678,124678,"
    "34678,134678,234678,1234678,15678,25678,125678,35678,235678,1235678,45678,145678,1245678,1345678,2345678"
).split(",")

_OCTANT_REUSE = {
    0: ' ', 255: '█',
    3: '\U0001FB82', 15: '▀', 63: '\U0001FB85',
    192: '▂', 240: '▄', 252: '▆',
    85: '▌', 170: '▐',
    5: '▘', 10: '▝', 80: '▖', 160: '▗',
    165: '▚', 90: '▞', 95: '▛', 175: '▜', 245: '▙', 250: '▟',
    1: ' ', 2: ' ', 20: ' ', 40: ' ', 64: ' ', 128: ' ',
}


def _build_octant_table():
    table = [None] * 256
    for i, name in enumerate(_OCTANT_NAMES):
        v = sum(1 << (int(c) - 1) for c in name)
        table[v] = chr(0x1CD00 + i)
    for v, ch in _OCTANT_REUSE.items():
        table[v] = ch
    return np.array(table, dtype='U1')


_OCTANT_CHARS = _build_octant_table()

from PIL import Image

CHARSETS = {
    'default': '@#$%&*+=-:. ',
    'blocks': '█▓▒░ ',
    'minimal': '@. ',
}

CHARSET_LABELS = {
    'default': '@#$%&*+=- .',
    'blocks': '█▓▒░ ',
    'minimal': '@. ',
    'custom': '(custom)',
}

COLOR_MODES = ['truecolor', '256', 'mono']
CHARSET_NAMES = ['default', 'blocks', 'minimal', 'custom']
DETAIL_MODES = ['sextant', 'octant', 'braille', 'quadblock', 'halfblock', 'ascii']

_LUT = None

_BAYER4 = (np.array([
    [0, 8, 2, 10],
    [12, 4, 14, 6],
    [3, 11, 1, 9],
    [15, 7, 13, 5],
], dtype=np.float64) / 16.0) - 0.5


def _get_lut():
    global _LUT
    if _LUT is None:
        lut = np.zeros((32, 32, 32), dtype=np.uint8)
        for ri in range(32):
            for gi in range(32):
                for bi in range(32):
                    lut[ri, gi, bi] = 16 + 36 * round(ri / 31 * 5) + 6 * round(gi / 31 * 5) + round(bi / 31 * 5)
        _LUT = lut
    return _LUT


def _dither(L, n_levels, strength=1.0):
    H, W = L.shape
    reps_y = H // 4 + 1
    reps_x = W // 4 + 1
    tile = np.tile(_BAYER4, (reps_y, reps_x))[:H, :W]
    bucket = 255.0 / max(n_levels - 1, 1)
    return np.clip(L + tile * bucket * strength, 0, 255)


def _runs(key_row):
    w = key_row.shape[0]
    change = np.empty(w, dtype=bool)
    change[0] = True
    if w > 1:
        change[1:] = key_row[1:] != key_row[:-1]
    starts = np.flatnonzero(change)
    ends = np.append(starts[1:], w)
    return starts, ends - starts


def render_frame(arr, charset, color_mode='truecolor', home=True, dither=False):
    H, W = arr.shape[:2]
    ca = np.array(list(charset), dtype='U1')
    n = len(charset)
    R = arr[:, :, 0].astype(np.int32)
    G = arr[:, :, 1].astype(np.int32)
    B = arr[:, :, 2].astype(np.int32)
    L = (R * 299 + G * 587 + B * 114) / 1000.0
    if dither:
        L = _dither(L, n)
    idx = (L * (n - 1) // 255).astype(np.int32).clip(0, n - 1)
    chars = ca[idx]
    buf = ['\033[H'] if home else []
    if color_mode == 'truecolor':
        packed = (R << 16 | G << 8 | B).astype(np.int64)
        key = idx.astype(np.int64) * (1 << 24) + packed
        for y in range(H):
            ry, gy, by, cy, ky = R[y], G[y], B[y], chars[y], key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(f'\033[38;2;{ry[x0]};{gy[x0]};{by[x0]}m{str(cy[x0]) * int(ln)}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    elif color_mode == '256':
        lut = _get_lut()
        ci = lut[(R >> 3).clip(0, 31), (G >> 3).clip(0, 31), (B >> 3).clip(0, 31)]
        key = idx.astype(np.int32) * 256 + ci
        for y in range(H):
            cy, ciy, ky = chars[y], ci[y], key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(f'\033[38;5;{ciy[x0]}m{str(cy[x0]) * int(ln)}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    else:
        for y in range(H):
            buf.append(''.join(chars[y]) + '\n')
    return ''.join(buf)


def render_frame_halfblock(arr, color_mode='truecolor', home=True):
    H, W = arr.shape[:2]
    if H % 2:
        arr = np.concatenate([arr, arr[-1:]], axis=0)
        H += 1
    rows = H // 2
    top = arr[0::2].astype(np.int32)
    bot = arr[1::2].astype(np.int32)
    buf = ['\033[H'] if home else []
    if color_mode == '256':
        lut = _get_lut()
        tR, tG, tB = top[:, :, 0], top[:, :, 1], top[:, :, 2]
        bR, bG, bB = bot[:, :, 0], bot[:, :, 1], bot[:, :, 2]
        tci = lut[(tR >> 3).clip(0, 31), (tG >> 3).clip(0, 31), (tB >> 3).clip(0, 31)]
        bci = lut[(bR >> 3).clip(0, 31), (bG >> 3).clip(0, 31), (bB >> 3).clip(0, 31)]
        key = tci.astype(np.int32) * 256 + bci
        for y in range(rows):
            tciy, bciy, ky = tci[y], bci[y], key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(f'\033[38;5;{tciy[x0]};48;5;{bciy[x0]}m{"▀" * ln}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    else:
        tR, tG, tB = top[:, :, 0], top[:, :, 1], top[:, :, 2]
        bR, bG, bB = bot[:, :, 0], bot[:, :, 1], bot[:, :, 2]
        tpacked = (tR << 16 | tG << 8 | tB).astype(np.int64)
        bpacked = (bR << 16 | bG << 8 | bB).astype(np.int64)
        key = tpacked * (1 << 24) + bpacked
        for y in range(rows):
            ry, gy, by = tR[y], tG[y], tB[y]
            rby, gby, bby = bR[y], bG[y], bB[y]
            ky = key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(
                    f'\033[38;2;{ry[x0]};{gy[x0]};{by[x0]};48;2;{rby[x0]};{gby[x0]};{bby[x0]}m{"▀" * ln}'
                )
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    return ''.join(buf)


def render_frame_sextant(arr, color_mode='truecolor', home=True):
    H, W = arr.shape[:2]
    if H % 3:
        pad = 3 - (H % 3)
        arr = np.concatenate([arr] + [arr[-1:]] * pad, axis=0)
        H += pad
    if W % 2:
        arr = np.concatenate([arr, arr[:, -1:]], axis=1)
        W += 1
    rows, cols = H // 3, W // 2
    TL = arr[0::3, 0::2].astype(np.float32)
    TR = arr[0::3, 1::2].astype(np.float32)
    ML = arr[1::3, 0::2].astype(np.float32)
    MR = arr[1::3, 1::2].astype(np.float32)
    BL = arr[2::3, 0::2].astype(np.float32)
    BR = arr[2::3, 1::2].astype(np.float32)

    def _lum(p):
        return p[:, :, 0] * 0.299 + p[:, :, 1] * 0.587 + p[:, :, 2] * 0.114

    cells = [TL, TR, ML, MR, BL, BR]
    lums = [_lum(c) for c in cells]
    mean_lum = sum(lums) / 6.0
    bits = [(l >= mean_lum).astype(np.uint8) for l in lums]
    pattern = bits[0]
    for i in range(1, 6):
        pattern = pattern | (bits[i] << i)
    chars = _SEXTANT_CHARS[pattern]
    pixels = np.stack(cells, axis=2)
    fg_mask = np.stack(bits, axis=2).astype(np.float32)
    bg_mask = 1.0 - fg_mask
    fg_cnt = fg_mask.sum(axis=2, keepdims=True).clip(min=1)
    bg_cnt = bg_mask.sum(axis=2, keepdims=True).clip(min=1)
    fg_col = ((pixels * fg_mask[:, :, :, np.newaxis]).sum(axis=2) / fg_cnt).clip(0, 255).astype(np.int32)
    bg_col = ((pixels * bg_mask[:, :, :, np.newaxis]).sum(axis=2) / bg_cnt).clip(0, 255).astype(np.int32)
    fR, fG, fB = fg_col[:, :, 0], fg_col[:, :, 1], fg_col[:, :, 2]
    bR, bG, bB = bg_col[:, :, 0], bg_col[:, :, 1], bg_col[:, :, 2]
    buf = ['\033[H'] if home else []
    if color_mode == '256':
        lut = _get_lut()
        fci = lut[(fR >> 3).clip(0, 31), (fG >> 3).clip(0, 31), (fB >> 3).clip(0, 31)]
        bci = lut[(bR >> 3).clip(0, 31), (bG >> 3).clip(0, 31), (bB >> 3).clip(0, 31)]
        key = pattern.astype(np.int32) * (256 * 256) + fci.astype(np.int32) * 256 + bci.astype(np.int32)
        for y in range(rows):
            chy, fciy, bciy, ky = chars[y], fci[y], bci[y], key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(f'\033[38;5;{fciy[x0]};48;5;{bciy[x0]}m{str(chy[x0]) * int(ln)}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    else:
        fpacked = (fR.astype(np.int64) << 16) | (fG.astype(np.int64) << 8) | fB.astype(np.int64)
        bpacked = (bR.astype(np.int64) << 16) | (bG.astype(np.int64) << 8) | bB.astype(np.int64)
        key = pattern.astype(np.int64) * (1 << 48) + fpacked * (1 << 24) + bpacked
        for y in range(rows):
            chy = chars[y]
            fry, fgy, fby = fR[y], fG[y], fB[y]
            bry, bgy, bby = bR[y], bG[y], bB[y]
            ky = key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(
                    f'\033[38;2;{fry[x0]};{fgy[x0]};{fby[x0]};'
                    f'48;2;{bry[x0]};{bgy[x0]};{bby[x0]}m'
                    f'{str(chy[x0]) * int(ln)}'
                )
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    return ''.join(buf)


def render_frame_quadblock(arr, color_mode='truecolor', home=True):
    H, W = arr.shape[:2]
    if H % 2:
        arr = np.concatenate([arr, arr[-1:]], axis=0)
        H += 1
    if W % 2:
        arr = np.concatenate([arr, arr[:, -1:]], axis=1)
        W += 1
    rows, cols = H // 2, W // 2
    UL = arr[0::2, 0::2].astype(np.float32)
    UR = arr[0::2, 1::2].astype(np.float32)
    LL = arr[1::2, 0::2].astype(np.float32)
    LR = arr[1::2, 1::2].astype(np.float32)

    def _lum(p):
        return p[:, :, 0] * 0.299 + p[:, :, 1] * 0.587 + p[:, :, 2] * 0.114

    mean_lum = (_lum(UL) + _lum(UR) + _lum(LL) + _lum(LR)) * 0.25
    b0 = (_lum(UL) >= mean_lum).astype(np.uint8)
    b1 = (_lum(UR) >= mean_lum).astype(np.uint8)
    b2 = (_lum(LL) >= mean_lum).astype(np.uint8)
    b3 = (_lum(LR) >= mean_lum).astype(np.uint8)
    pattern = (b0 | (b1 << 1) | (b2 << 2) | (b3 << 3))
    chars = _QUAD_CHARS[pattern]
    pixels = np.stack([UL, UR, LL, LR], axis=2)
    fg_mask = np.stack([b0, b1, b2, b3], axis=2).astype(np.float32)
    bg_mask = 1.0 - fg_mask
    fg_cnt = fg_mask.sum(axis=2, keepdims=True).clip(min=1)
    bg_cnt = bg_mask.sum(axis=2, keepdims=True).clip(min=1)
    fg_col = ((pixels * fg_mask[:, :, :, np.newaxis]).sum(axis=2) / fg_cnt).clip(0, 255).astype(np.int32)
    bg_col = ((pixels * bg_mask[:, :, :, np.newaxis]).sum(axis=2) / bg_cnt).clip(0, 255).astype(np.int32)
    fR, fG, fB = fg_col[:, :, 0], fg_col[:, :, 1], fg_col[:, :, 2]
    bR, bG, bB = bg_col[:, :, 0], bg_col[:, :, 1], bg_col[:, :, 2]
    buf = ['\033[H'] if home else []
    if color_mode == '256':
        lut = _get_lut()
        fci = lut[(fR >> 3).clip(0, 31), (fG >> 3).clip(0, 31), (fB >> 3).clip(0, 31)]
        bci = lut[(bR >> 3).clip(0, 31), (bG >> 3).clip(0, 31), (bB >> 3).clip(0, 31)]
        key = pattern.astype(np.int32) * (256 * 256) + fci.astype(np.int32) * 256 + bci.astype(np.int32)
        for y in range(rows):
            chy, fciy, bciy, ky = chars[y], fci[y], bci[y], key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(f'\033[38;5;{fciy[x0]};48;5;{bciy[x0]}m{str(chy[x0]) * ln}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    else:
        fpacked = (fR.astype(np.int64) << 16) | (fG.astype(np.int64) << 8) | fB.astype(np.int64)
        bpacked = (bR.astype(np.int64) << 16) | (bG.astype(np.int64) << 8) | bB.astype(np.int64)
        key = pattern.astype(np.int64) * (1 << 48) + fpacked * (1 << 24) + bpacked
        for y in range(rows):
            chy = chars[y]
            fry, fgy, fby = fR[y], fG[y], fB[y]
            bry, bgy, bby = bR[y], bG[y], bB[y]
            ky = key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(
                    f'\033[38;2;{fry[x0]};{fgy[x0]};{fby[x0]};'
                    f'48;2;{bry[x0]};{bgy[x0]};{bby[x0]}m'
                    f'{str(chy[x0]) * ln}'
                )
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    return ''.join(buf)


_OCTANT_SSX = 4
_OCTANT_SSY = 4


def _octant_base_grid(arr):
    ssx, ssy = _OCTANT_SSX, _OCTANT_SSY
    H, W = arr.shape[:2]
    gh, gw = 4 * ssy, 2 * ssx
    if H % gh:
        pad = gh - (H % gh)
        arr = np.concatenate([arr] + [arr[-1:]] * pad, axis=0)
        H += pad
    if W % gw:
        pad = gw - (W % gw)
        arr = np.concatenate([arr, arr[:, -1:].repeat(pad, axis=1)], axis=1)
        W += pad
    rows, cols = H // gh, W // gw
    base_h, base_w = rows * 4, cols * 2
    a = arr.reshape(base_h, ssy, base_w, ssx, 3).astype(np.float32).mean(axis=(1, 3))
    return a, rows, cols


def render_frame_octant(arr, color_mode='truecolor', home=True):
    a, rows, cols = _octant_base_grid(arr)

    d1 = a[0::4, 0::2]
    d2 = a[0::4, 1::2]
    d3 = a[1::4, 0::2]
    d4 = a[1::4, 1::2]
    d5 = a[2::4, 0::2]
    d6 = a[2::4, 1::2]
    d7 = a[3::4, 0::2]
    d8 = a[3::4, 1::2]

    bits, fg_col, bg_col = _cluster2([d1, d2, d3, d4, d5, d6, d7, d8])
    pattern = np.zeros(bits.shape[:2], dtype=np.int32)
    for i in range(8):
        pattern |= (bits[:, :, i].astype(np.int32) << i)
    chars = _OCTANT_CHARS[pattern]

    fR, fG, fB = fg_col[:, :, 0], fg_col[:, :, 1], fg_col[:, :, 2]
    bR, bG, bB = bg_col[:, :, 0], bg_col[:, :, 1], bg_col[:, :, 2]

    buf = ['\033[H'] if home else []
    if color_mode == '256':
        lut = _get_lut()
        fci = lut[(fR >> 3).clip(0, 31), (fG >> 3).clip(0, 31), (fB >> 3).clip(0, 31)]
        bci = lut[(bR >> 3).clip(0, 31), (bG >> 3).clip(0, 31), (bB >> 3).clip(0, 31)]
        key = pattern.astype(np.int32) * (256 * 256) + fci.astype(np.int32) * 256 + bci.astype(np.int32)
        for y in range(rows):
            chy, fciy, bciy, ky = chars[y], fci[y], bci[y], key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(f'\033[38;5;{fciy[x0]};48;5;{bciy[x0]}m{str(chy[x0]) * int(ln)}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    else:
        fpacked = (fR.astype(np.int64) << 16) | (fG.astype(np.int64) << 8) | fB.astype(np.int64)
        bpacked = (bR.astype(np.int64) << 16) | (bG.astype(np.int64) << 8) | bB.astype(np.int64)
        key = pattern.astype(np.int64) * (1 << 48) + fpacked * (1 << 24) + bpacked
        for y in range(rows):
            chy = chars[y]
            fry, fgy, fby = fR[y], fG[y], fB[y]
            bry, bgy, bby = bR[y], bG[y], bB[y]
            ky = key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(
                    f'\033[38;2;{fry[x0]};{fgy[x0]};{fby[x0]};'
                    f'48;2;{bry[x0]};{bgy[x0]};{bby[x0]}m'
                    f'{str(chy[x0]) * int(ln)}'
                )
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    return ''.join(buf)


def _cluster2(cells, iters=5):
    def _lum(p):
        return p[:, :, 0] * 0.299 + p[:, :, 1] * 0.587 + p[:, :, 2] * 0.114

    N = len(cells)
    pixels = np.stack(cells, axis=2)
    lums = np.stack([_lum(c) for c in cells], axis=2)
    mean_lum = lums.mean(axis=2, keepdims=True)
    bits = (lums >= mean_lum).astype(np.float32)

    for _ in range(iters):
        fg_cnt = bits.sum(axis=2, keepdims=True).clip(min=1)
        bg_cnt = (N - bits.sum(axis=2, keepdims=True)).clip(min=1)
        fg_mask = bits[:, :, :, np.newaxis]
        bg_mask = 1.0 - fg_mask
        c_fg = (pixels * fg_mask).sum(axis=2) / fg_cnt
        c_bg = (pixels * bg_mask).sum(axis=2) / bg_cnt
        d_fg = ((pixels - c_fg[:, :, np.newaxis, :]) ** 2).sum(axis=3)
        d_bg = ((pixels - c_bg[:, :, np.newaxis, :]) ** 2).sum(axis=3)
        bits = (d_fg <= d_bg).astype(np.float32)

    fg_cnt = bits.sum(axis=2, keepdims=True).clip(min=1)
    bg_cnt = (N - bits.sum(axis=2, keepdims=True)).clip(min=1)
    fg_mask = bits[:, :, :, np.newaxis]
    bg_mask = 1.0 - fg_mask
    fg_col = ((pixels * fg_mask).sum(axis=2) / fg_cnt).clip(0, 255).astype(np.int32)
    bg_col = ((pixels * bg_mask).sum(axis=2) / bg_cnt).clip(0, 255).astype(np.int32)
    return bits.astype(np.uint8), fg_col, bg_col


def render_frame_braille(arr, color_mode='truecolor', home=True):
    ssx, ssy = _BRAILLE_SSX, _BRAILLE_SSY
    H, W = arr.shape[:2]
    gh, gw = 4 * ssy, 2 * ssx
    if H % gh:
        pad = gh - (H % gh)
        arr = np.concatenate([arr] + [arr[-1:]] * pad, axis=0)
        H += pad
    if W % gw:
        pad = gw - (W % gw)
        arr = np.concatenate([arr, arr[:, -1:].repeat(pad, axis=1)], axis=1)
        W += pad
    rows, cols = H // gh, W // gw

    base_h, base_w = rows * 4, cols * 2
    a = arr.reshape(base_h, ssy, base_w, ssx, 3).astype(np.float32).mean(axis=(1, 3))

    dot1 = a[0::4, 0::2]
    dot2 = a[1::4, 0::2]
    dot3 = a[2::4, 0::2]
    dot4 = a[0::4, 1::2]
    dot5 = a[1::4, 1::2]
    dot6 = a[2::4, 1::2]
    dot7 = a[3::4, 0::2]
    dot8 = a[3::4, 1::2]

    bits, fg_col, bg_col = _cluster2([dot1, dot2, dot3, dot4, dot5, dot6, dot7, dot8])
    pattern = np.zeros(bits.shape[:2], dtype=np.int32)
    for i in range(8):
        pattern |= (bits[:, :, i].astype(np.int32) << i)
    chars = _BRAILLE_CHARS[pattern]

    fR, fG, fB = fg_col[:, :, 0], fg_col[:, :, 1], fg_col[:, :, 2]
    bR, bG, bB = bg_col[:, :, 0], bg_col[:, :, 1], bg_col[:, :, 2]

    buf = ['\033[H'] if home else []
    if color_mode == '256':
        lut = _get_lut()
        fci = lut[(fR >> 3).clip(0, 31), (fG >> 3).clip(0, 31), (fB >> 3).clip(0, 31)]
        bci = lut[(bR >> 3).clip(0, 31), (bG >> 3).clip(0, 31), (bB >> 3).clip(0, 31)]
        key = pattern.astype(np.int32) * (256 * 256) + fci.astype(np.int32) * 256 + bci.astype(np.int32)
        for y in range(rows):
            chy, fciy, bciy, ky = chars[y], fci[y], bci[y], key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(f'\033[38;5;{fciy[x0]};48;5;{bciy[x0]}m{str(chy[x0]) * int(ln)}')
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    else:
        fpacked = (fR.astype(np.int64) << 16) | (fG.astype(np.int64) << 8) | fB.astype(np.int64)
        bpacked = (bR.astype(np.int64) << 16) | (bG.astype(np.int64) << 8) | bB.astype(np.int64)
        key = pattern.astype(np.int64) * (1 << 48) + fpacked * (1 << 24) + bpacked
        for y in range(rows):
            chy = chars[y]
            fry, fgy, fby = fR[y], fG[y], fB[y]
            bry, bgy, bby = bR[y], bG[y], bB[y]
            ky = key[y]
            starts, lengths = _runs(ky)
            parts = []
            for x0, ln in zip(starts, lengths):
                parts.append(
                    f'\033[38;2;{fry[x0]};{fgy[x0]};{fby[x0]};'
                    f'48;2;{bry[x0]};{bgy[x0]};{bby[x0]}m'
                    f'{str(chy[x0]) * int(ln)}'
                )
            buf.append(''.join(parts))
            buf.append('\033[0m\n')
    return ''.join(buf)


_char_count = 0


def note_chars(n):
    global _char_count
    _char_count += n


def take_char_count():
    global _char_count
    n = _char_count
    _char_count = 0
    return n


def resolve_detail_mode(settings):
    if settings.get('color', 'truecolor') == 'mono':
        return 'ascii'
    mode = settings.get('detail', 'sextant')
    return mode if mode in DETAIL_MODES else 'sextant'


def char_aspect_for(mode):
    return 2.0


def resize_for_terminal(arr, w, h):
    img = Image.fromarray(arr.astype(np.uint8), 'RGB')
    return np.asarray(img.resize((w, h), Image.LANCZOS))


def calc_render_size(iw, ih, tw, th, user_w=None, char_aspect=2.0):
    rw = min(user_w or tw, tw)
    aspect = iw / max(ih, 1)
    rh = max(1, int(rw / (aspect * char_aspect)))
    maxh = max(th - 2, 1)
    if rh > maxh:
        rh = maxh
        rw = max(1, min(tw, int(rh * aspect * char_aspect)))
    return max(1, rw), max(1, rh)
