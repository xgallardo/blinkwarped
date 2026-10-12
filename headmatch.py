"""Mide el tamaño relativo de la cabeza entre tiras buscando la cabeza de la pose de guardia
(plantilla) en cada cuadro a distintas escalas (correlacion cruzada normalizada)."""
import numpy as np
from PIL import Image
from scipy.signal import fftconvolve

D = 0.25  # se trabaja a 1/4 de resolucion para que sea rapido

def gray(crop_rgba):
    a = crop_rgba.astype(float)
    lum = (a[:, :, 0] * .3 + a[:, :, 1] * .59 + a[:, :, 2] * .11) / 255
    al = a[:, :, 3] / 255
    return lum * al + (1 - al) * 0.5   # fondo gris medio: el contorno cuenta

def small(arr, s):
    im = Image.fromarray(arr.astype(np.uint8), 'RGBA')
    w, h = max(1, round(im.width * s)), max(1, round(im.height * s))
    return np.array(im.resize((w, h), Image.LANCZOS))

def head_patch(frame_rgba, mask):
    ys, xs = np.nonzero(mask); y0, y1 = ys.min(), ys.max(); h = y1 - y0
    top = mask[y0:y0 + int(.22 * h)]
    cx = int(np.nonzero(top[: max(1, h // 8)])[1].mean())
    half = int(.16 * h)
    x0, x1 = max(0, cx - half), min(mask.shape[1], cx + half)
    return frame_rgba[y0:y0 + int(.24 * h), x0:x1]

def ncc_max(img, tpl):
    th, tw = tpl.shape
    if img.shape[0] < th or img.shape[1] < tw: return -1
    t = tpl - tpl.mean(); tn = np.sqrt((t ** 2).sum())
    if tn == 0: return -1
    num = fftconvolve(img, t[::-1, ::-1], mode='valid')
    ones = np.ones_like(tpl)
    s1 = fftconvolve(img, ones, mode='valid'); s2 = fftconvolve(img ** 2, ones, mode='valid')
    var = np.maximum(s2 - s1 ** 2 / tpl.size, 1e-9)
    return float((num / (np.sqrt(var) * tn)).max())

SCALES = np.arange(0.6, 1.62, 0.02)

def best_scale(ref_patch, frame_rgba, mask):
    """Escala de la cabeza del cuadro respecto de la plantilla (1 = mismo tamaño)."""
    ys, xs = np.nonzero(mask); y0, y1 = ys.min(), ys.max()
    x0, x1 = xs.min(), xs.max()
    region = frame_rgba[y0:y0 + int(.55 * (y1 - y0)) + 1, x0:x1 + 1]   # mitad superior: ahi esta la cabeza
    img = gray(small(region, D))
    best = (-1, 1)
    for s in SCALES:
        tpl = gray(small(ref_patch, D * s))
        if tpl.shape[0] < 4 or tpl.shape[1] < 4: continue
        v = ncc_max(img, tpl)
        if v > best[0]: best = (v, s)
    return best
