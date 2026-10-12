# Maqueta larga de como acomodar el paquete en un proyecto de Behance (ancho 1400 px).
# Cada bloque muestra un cuadro de la pieza real, con una etiqueta del archivo que va ahi.
import os, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import make_behance as mb
B = mb.OUT; W = 1400; GAP = 40; BG = (14, 14, 16)
blocks = []

def frame(path, i=None):
    im = Image.open(os.path.join(B, path))
    if getattr(im, 'n_frames', 1) > 1: im.seek(i if i is not None else im.n_frames // 2)
    return im.convert('RGB')

def tag(img, s, kind):
    d = ImageDraw.Draw(img); f = mb.font(14)
    label = f'{kind}  ·  {s}'; w = int(f.getlength(label)) + 24
    d.rectangle((12, img.height - 40, 12 + w, img.height - 12), fill=(0, 0, 0))
    d.text((24, img.height - 26), label, font=f, fill=(255, 210, 79) if kind != 'PNG' else (242, 242, 242), anchor='lm')

def full(path, kind=None, i=None):
    im = frame(path, i); im = im.resize((W, round(im.height * W / im.width)), Image.LANCZOS)
    tag(im, path, kind or ('GIF' if path.endswith('.gif') else 'PNG')); blocks.append(im)

def row(paths, h=None, i=None):
    ims = [frame(p, i) for p in paths]; n = len(ims); gap = 16; cw = (W - gap * (n - 1)) // n
    ims = [im.resize((cw, round(im.height * cw / im.width)), Image.LANCZOS) for im in ims]
    rh = max(im.height for im in ims); r = Image.new('RGB', (W, rh), BG)
    for k, (im, p) in enumerate(zip(ims, paths)):
        tag(im, os.path.basename(p), 'GIF' if p.endswith('.gif') else 'PNG'); r.paste(im, (k * (cw + gap), 0))
    blocks.append(r)

def title(name):
    t = Image.open(os.path.join(B, 'titulos', name + '-transparente.png')).convert('RGBA')
    t = t.resize((900, round(t.height * 900 / t.width)), Image.LANCZOS)
    r = Image.new('RGB', (W, t.height + 80), BG); r.paste(t, ((W - t.width) // 2, 40), t); blocks.append(r)

def note(s):
    r = Image.new('RGB', (W, 70), BG); ImageDraw.Draw(r).text((W // 2, 35), s, font=mb.font(16), fill=(154, 154, 154), anchor='mm'); blocks.append(r)

def video(path, t):
    import subprocess, tempfile
    tmp = os.path.join(tempfile.gettempdir(), 'reelframe.png')
    subprocess.run([mb.FFMPEG, '-loglevel', 'error', '-y', '-ss', str(t), '-i', os.path.join(B, path), '-frames:v', '1', tmp], check=True)
    return Image.open(tmp).convert('RGB')

# 1 portada: intro animada
full('intro-1400.gif', i=10); note('Portada del proyecto: la intro animada a todo el ancho')
# 2 reel horizontal
im = video('reel-16x9.mp4', 14); im = im.resize((W, 788)); tag(im, 'reel-16x9.mp4', 'VIDEO'); blocks.append(im)
note('Reel de 30 s con musica (subir como video o embed de YouTube/Vimeo)')
# 3 poster + logo
p = frame('poster-personajes-9x16.png').resize((620, 1102), Image.LANCZOS); tag(p, 'poster-personajes-9x16.png', 'PNG')
lg = Image.open(os.path.join(B, 'logos', 'logo.png')).convert('RGBA'); lg.thumbnail((640, 640))
r = Image.new('RGB', (W, 1102), BG); r.paste(p, (60, 0)); r.paste(lg, (60 + 620 + (W - 680 - lg.width) // 2, (1102 - lg.height) // 2), lg)
ImageDraw.Draw(r).text((60 + 620 + (W - 680) // 2, 1102 - 80), 'logos/logo-animado.gif', font=mb.font(14), fill=(255, 210, 79), anchor='mm'); blocks.append(r)
# 4 personajes
title('the-characters')
for c in ('mark', 'tom', 'travis'): full(f'gifs/heroes-16x9/{c}-movimientos.gif', i=60)
row([f'gifs/heroes-16x9/{c}-todas-las-animaciones.gif' for c in ('mark', 'tom', 'travis')], i=6)
# 5 enemigos
title('the-enemies')
ids = ['darkness', 'hardman', 'juggalo', 'mortalcore', 'punx', 'screamguy', 'skinman', 'trashrat', 'warrior']
for k in range(0, 9, 3): row([f'gifs/enemigo-{c}.gif' for c in ids[k:k + 3]], i=20)
# 6 jefe
title('the-boss'); row(['gifs/jefe-box-car-tom.gif', 'gifs/pelea-jefe-box-car-tom.gif'], i=30)
# 7 escenarios
title('the-stages')
for k in (1, 2): full(f'fondos/recorrido-panoramico-{k}.png')
row([f'fondos/zona-{k}-16x9.png' for k in (1, 3, 6)])
# 8 peleas
title('the-fights'); full('gifs/seleccion.gif', i=20)
for k, c in ((1, 'mark'), (2, 'tom'), (3, 'travis')): full(f'gifs/pelea-{k}-{c}.gif', i=35)
# 9 cierre
full('banda/banda-en-vivo.gif', i=3)
im = video('reel-9x16.mp4', 9); im = im.resize((540, 960)); tag(im, 'reel-9x16.mp4', 'VIDEO')
r = Image.new('RGB', (W, 960), BG); r.paste(im, ((W - 540) // 2, 0)); blocks.append(r)
note('Reel vertical para Instagram / Reels, al final o como enlace')

H = sum(b.height for b in blocks) + GAP * (len(blocks) + 1)
out = Image.new('RGB', (W, H), BG); y = GAP
for b in blocks: out.paste(b, (0, y)); y += b.height + GAP
path = os.path.join(B, 'maqueta-behance.jpg'); out.save(path, quality=86, optimize=True)
print(path, out.size, round(os.path.getsize(path) / 1e6, 1), 'MB')
