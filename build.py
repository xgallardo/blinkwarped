"""Corta las tiras de sprites, iguala sus tamaños, arma un atlas por personaje y genera
index.html (un solo archivo, con las imagenes incrustadas). Uso: python3 build.py"""
import base64, io, json, os
import numpy as np
from PIL import Image
from scipy import ndimage
import headmatch as hm

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
HERE = os.path.dirname(os.path.abspath(__file__))
SCALE = 0.26          # tamano final del sprite respecto al original (atlas a 2x del mundo)
LYING = {'fall', 'getup', 'defeat'}   # animaciones ancladas al centro del cuerpo
FALLS = 'ENEMIGOS/CAIDAS Y LEVANTADAS'

# Cada animacion: (numero de la tira, cuadros) o (numero, cuadros, carpeta distinta)
CHARS = {
  'mark': ('SPRITE MARK', {
    'idle': (1, 4), 'walk': (2, 6), 'jab': (3, 4), 'cross': (4, 4), 'kick': (5, 4), 'jump': (6, 4),
    'airkick': (7, 4), 'hurt': (8, 3), 'fall': (9, 4), 'getup': (10, 4), 'defeat': (11, 3), 'special': (12, 4)}),
  'tom': ('SPRITE TOM', {
    'idle': (1, 4), 'walk': (2, 6), 'jab': (3, 4), 'cross': (4, 4), 'kick': (5, 4), 'jump': (6, 4),
    'hurt': (7, 3), 'airkick': (8, 4), 'fall': (9, 4), 'getup': (10, 4), 'defeat': (11, 3), 'special': (12, 4)}),
  'travis': ('SPRITE TRAVIS', {
    'idle': (1, 4), 'walk': (2, 6), 'jab': (3, 4), 'cross': (4, 4), 'kick': (5, 4), 'jump': (6, 4),
    'special': (7, 4), 'airkick': (8, 4), 'hurt': (9, 3), 'fall': (10, 4), 'getup': (11, 4), 'defeat': (12, 3)}),
}

# Enemigos: todos dibujados mirando a la izquierda. Las caidas y levantadas estan en FALLS.
# Repetidas sin usar en FALLS: 7 (mortalcore), 5 y 8 (juggalo, mal orientadas), 15 (punx), 23 (juggalo).
def foe(folder, walk, punch, kick, jump, fall, getup):
    return ('ENEMIGOS/' + folder, {'walk': (walk, 6), 'punch': (punch, 4), 'kick': (kick, 4), 'jump': (jump, 4),
                                   'fall': (fall, 5, FALLS), 'getup': (getup, 5, FALLS)})
ENEMIES = {
  'darkness':   foe('DARKNESS', 1, 2, 3, 4, 1, 3),
  'hardman':    foe('HARDMAN', 21, 22, 23, 24, 2, 4),
  'juggalo':    foe('JUGGALO', 15, 16, 17, 18, 9, 11),   # caida 9: en la 5 y la 8 el golpe esta dibujado mirando al otro lado
  'mortalcore': foe('MORTALCORE', 10, 11, 12, 13, 6, 10),
  'punx':       foe('PUNX', 6, 7, 8, 9, 14, 18),
  'screamguy':  foe('SCREAM GUY', 16, 17, 18, 19, 12, 13),
  'skinman':    foe('SKIN MAN', 12, 13, 14, 15, 16, 17),
  'trashrat':   foe('TRASH RAT', 6, 7, 8, 11, 19, 21),
  'warrior':    foe('WARRIOR', 1, 2, 3, 4, 20, 22),
}
# Villano principal (mira a la izquierda). Repetidas sin usar: 6 (salto), 9 (guitarra), 11 (caida).
VILLAIN = ('VILLANO PRINCIPAL', {'idle': (8, 4), 'walk': (2, 6), 'punch': (1, 4), 'kick': (4, 4), 'jump': (3, 4),
                                 'guitar': (5, 6), 'fall': (7, 5), 'getup': (10, 5)})

# Para medir la cabeza en tiras donde esta tirado, solo se usan los cuadros de pie o sentado
STANDING = {'fall': [0, 1], 'getup': [-1], 'defeat': [0]}
STANDING_HEROES = {'fall': [0], 'getup': [-1], 'defeat': [0]}  # en los heroes el cuadro 1 de la caida ya va en el aire

def find(folder, spec):
    num, folder = spec[0], (spec[2] if len(spec) > 2 else folder)
    for f in sorted(os.listdir(os.path.join(ROOT, folder))):
        p = os.path.join(ROOT, folder, f)
        if f.lower().endswith('.png') and f.rsplit('-', 1)[-1] == f'{num}.png' and Image.open(p).width > 1500:
            return p
    raise FileNotFoundError(f'{folder} #{num}')

def frame_masks(path, n):
    """Separa la tira en n cuadros: cada mancha va al cuadro donde cae su centro."""
    a = np.array(Image.open(path).convert('RGBA'))
    mask = a[:, :, 3] > 20
    lab, _ = ndimage.label(mask, structure=np.ones((3, 3)))
    cw = a.shape[1] / n; cells = [np.zeros_like(mask) for _ in range(n)]
    for i, sl in enumerate(ndimage.find_objects(lab), 1):
        comp = lab[sl] == i; xs = np.nonzero(comp)[1]
        cells[min(n - 1, int((sl[1].start + xs.mean()) // cw))][sl] |= comp
    return a, cells

def cut(path, n, lying, sc):
    a, cells = frame_masks(path, n); out = []
    for m in cells:
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        crop = a[y0:y1, x0:x1].copy(); crop[~m[y0:y1, x0:x1]] = 0
        if lying:
            ax = (x1 - x0) / 2
        else:   # centro de la cabeza: franja superior del cuerpo
            top = m[y0:y0 + max(1, (y1 - y0) // 5), x0:x1]
            ax = np.nonzero(top)[1].mean()
        img = Image.fromarray(crop)
        w, h = max(1, round(img.width * sc)), max(1, round(img.height * sc))
        out.append((img.resize((w, h), Image.LANCZOS), ax * sc, h))
    return out

# --- igualar tamaños: se busca la cabeza de la guardia en cada tira (ver headmatch.py) ---
CACHE_PATH = os.path.join(HERE, '.headcache.json')
try: CACHE = json.load(open(CACHE_PATH))
except Exception: CACHE = {}

def head_scales(name, folder, anims, ref, standing=STANDING):
    """Tamaño de la cabeza de cada tira relativo a la tira de guardia (1 = igual)."""
    rpath = find(folder, anims[ref]); a, cells = frame_masks(rpath, anims[ref][1])
    patch = hm.head_patch(a, cells[0]); out = {}
    for an, spec in anims.items():
        path = find(folder, spec)
        key = f'{name}|{ref}|{os.path.basename(rpath)}|{os.path.getmtime(rpath)}|{os.path.basename(path)}|{os.path.getmtime(path)}|{an}|{standing.get(an)}'
        if key not in CACHE:
            a2, cells2 = frame_masks(path, spec[1])
            idx = standing.get(an, range(len(cells2)))
            res = [hm.best_scale(patch, a2, cells2[i]) for i in idx]
            good = [s for v, s in res if v > .55]
            CACHE[key] = float(np.median(good if good else [s for v, s in res]))
        out[an] = CACHE[key]
    return out

def pack(frames, maxw=2048):
    x = y = rowh = 0; pos = []
    for img, _, _ in frames:
        if x + img.width + 2 > maxw: x = 0; y += rowh + 2; rowh = 0
        pos.append((x, y)); x += img.width + 2; rowh = max(rowh, img.height)
    sheet = Image.new('RGBA', (maxw, y + rowh), (0, 0, 0, 0))
    for (img, _, _), (px, py) in zip(frames, pos): sheet.paste(img, (px, py))
    return sheet, pos

# Imagenes en WebP (con transparencia): ~70% mas livianas que PNG sin perdida visible
WEBP_Q = 90
def uri(img, q=WEBP_Q):
    b = io.BytesIO(); img.save(b, 'WEBP', quality=q, method=4)
    return 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode()

# Tamano en pantalla de cada enemigo (igual que 'size' en FOES de game_template.html). El atlas se guarda con
# esa resolucion extra para que al agrandarlo en el juego no se pixele.
FOE_SIZE = {'darkness': 1.2, 'hardman': 1.2, 'juggalo': 1.2, 'skinman': 1.1, 'trashrat': 1.1, 'villain': 1.89}

def build_set(name, folder, anims, ref, standing=STANDING, size=1.0):
    """Todas las tiras quedan con la cabeza del mismo tamaño (la mediana de las tiras del personaje)."""
    rel = head_scales(name, folder, anims, ref, standing)
    # caida y levantada vienen en pareja: la caida no se agranda mas de 15% sobre la levantada
    if 'fall' in rel and 'getup' in rel: rel['fall'] = max(rel['fall'], rel['getup'] / 1.15)
    avg = float(np.median(list(rel.values())))  # mediana: una tira muy distinta no mueve el tamaño general
    print(f'  {name}: ' + ' '.join(f'{an} x{avg / r:.2f}' for an, r in rel.items()))
    flat, index = [], {}
    for an, spec in anims.items():
        fr = cut(find(folder, spec), spec[1], an in LYING, SCALE * avg / rel[an] * size)
        index[an] = list(range(len(flat), len(flat) + len(fr))); flat += fr
    sheet, pos = pack(flat)
    meta = {an: [dict(x=pos[i][0], y=pos[i][1], w=flat[i][0].width, h=flat[i][0].height,
                      ax=round(flat[i][1], 1), ay=flat[i][2]) for i in idx] for an, idx in index.items()}
    # avatar: cuadrado alrededor de la cabeza en el primer cuadro de guardia (o golpe), relativo al cuadro
    ref_an = 'idle' if 'idle' in index else 'punch'
    fimg = flat[index[ref_an][0]][0]; al = np.array(fimg)[:, :, 3] > 20
    top = np.nonzero(al.any(1))[0][0]; hh = round(fimg.height * .30)
    cols = np.nonzero(al[top:top + round(fimg.height * .2)].any(0))[0]
    cx = (cols[0] + cols[-1]) / 2; side = max(cols[-1] - cols[0], hh) * 1.12
    face = [round(cx - side / 2), max(0, round(top - side * .06)), round(side)]
    return {'img': uri(sheet), 'anims': meta, 'res': 2 * size, 'face': face}   # res: pixeles del atlas por unidad del mundo

# Heroes con el doble de resolucion: se ven nitidos aunque el juego se agrande mucho (pantallas grandes / retina)
HERO_RES = 2.0
data = {'chars': {n: build_set(n, f, a, 'idle', STANDING_HEROES, size=HERO_RES) for n, (f, a) in CHARS.items()},
        'enemies': {n: build_set(n, f, a, 'punch', size=FOE_SIZE.get(n, 1)) for n, (f, a) in ENEMIES.items()}}
data['enemies']['villain'] = build_set('villain', *VILLAIN, 'idle', size=FOE_SIZE['villain'])
json.dump(CACHE, open(CACHE_PATH, 'w'))

# efecto especial: grilla 4x2, se ancla abajo al centro
fx = Image.open(os.path.join(ROOT, 'SPRITE MOVIMIENTO ESPECIAL', 'Aura energética pixelada en ocho fotogramas-1.png')).convert('RGBA')
fw, fh = fx.width // 4, fx.height // 2; FXS = 0.42; fxf = []
for r in range(2):
    for c in range(4):
        fxf.append(fx.crop((c * fw, r * fh, (c + 1) * fw, (r + 1) * fh)).resize((round(fw * FXS), round(fh * FXS)), Image.LANCZOS))
fxs = Image.new('RGBA', (fxf[0].width * 8, fxf[0].height), (0, 0, 0, 0))
for i, f in enumerate(fxf): fxs.paste(f, (i * f.width, 0))
bottom = int(np.nonzero(np.array(fx)[:, :, 3].max(1) > 40)[0].max() % fh * FXS)
data['fx'] = {'img': uri(fxs), 'w': fxf[0].width, 'h': fxf[0].height, 'by': bottom}

# --- Escenario por capas (parallax). Se guardan a 2x del mundo (el juego dibuja a ancho/2 x alto/2).
# Cada capa: archivo, escala (mundo por pixel original), y (posicion vertical en el mundo),
# f (velocidad respecto de la camara: 0 quieta, 1 igual que el piso), mirror (repetir espejado), drift (nubes).
def uri_jpg(img, q=86):   # imagenes opacas (cielo, suelo, final): WebP sin canal alfa
    return uri(img.convert('RGB'), q)
def layer_img(fname, k, jpg=False, crop_h=None):
    im = Image.open(os.path.join(ROOT, 'ESCENARIO', fname)).convert('RGBA')
    if crop_h: im = im.crop((0, 0, im.width, min(im.height, crop_h)))   # solo la parte que se ve
    im = im.resize((round(im.width * k * 2), round(im.height * k * 2)), Image.LANCZOS)
    return uri_jpg(im) if jpg else uri(im)
LAYERS = [  # de atras hacia adelante
  dict(file='Horizonte pixelado bajo cielo azul.png', k=.38, y=-189, f=.08, jpg=True),   # ciudad sobre las carpas (base ~y85)
  dict(file='Capa de nubes pixeladas en 8 bits.png', k=.3, y=-74, f=.18, drift=.04),
  dict(file='Palmeras, autobuses y rampas pixeladas.png', k=.32, y=-80, f=.45, mirror=True),  # palmeras asoman sobre las carpas
  dict(file='publico.png', k=.13, y=86, f=.7),   # publico de fondo: tapa los huecos de cielo entre carpas (pies ~y166)
  dict(file='suelo.png', k=.32, y=165, f=1, mirror=True, jpg=True, crop_h=340),  # 20% mas chico; se ven ~105 de alto: 328 px
]
# Capa cercana: fondo-final.png, una tira continua (carpas, valla, publico). Base de la valla en Y~560.
# Es muy ancha para una sola imagen en el navegador: se corta en trozos de 2048 px que se dibujan seguidos.
NEAR_FILE, NEAR_K, NEAR_BASE_PX, FLOOR_TOP, CHUNK = 'fondo-final.png', .384, 560, 176, 2048   # .32 + 20%
def near_chunks():
    im = Image.open(os.path.join(ROOT, 'ESCENARIO', NEAR_FILE)).convert('RGBA')
    im = im.resize((round(im.width * NEAR_K * 2), round(im.height * NEAR_K * 2)), Image.LANCZOS)
    return [uri(im.crop((x, 0, min(im.width, x + CHUNK), im.height))) for x in range(0, im.width, CHUNK)]
data['bg'] = {
  'layers': [dict(img=layer_img(L['file'], L['k'], L.get('jpg'), L.get('crop_h')), y=L['y'], f=L['f'],
                  mirror=L.get('mirror', False), drift=L.get('drift', 0)) for L in LAYERS],
  'near': near_chunks(),
  'nearY': FLOOR_TOP - NEAR_BASE_PX * NEAR_K,
}
# Capa delantera (ESCENARIO/CERCANOS): publico en siluetas delante de los luchadores, animado con
# las imagenes de la carpeta (en orden alfabetico). Abajo de la pantalla y algo mas rapida que el piso.
FRONT_K, FRONT_F = .156, 1.3   # .13 + 20%
front_dir = os.path.join(ROOT, 'ESCENARIO', 'CERCANOS')
front_files = sorted(f for f in os.listdir(front_dir) if f.lower().endswith('.png')) if os.path.isdir(front_dir) else []
if any(f.startswith('publico-loop') for f in front_files):   # si estan los cuadros del loop, solo esos
    front_files = [f for f in front_files if f.startswith('publico-loop')]
if front_files:
    data['bg']['front'] = dict(imgs=[layer_img(os.path.join('CERCANOS', f), FRONT_K) for f in front_files],
                               y=270 + 4 - 724 * FRONT_K, f=FRONT_F)
print('escenario:', len(LAYERS), 'capas de fondo +', NEAR_FILE, 'en', len(data['bg']['near']), 'trozos')
print('capa delantera:', len(front_files), 'cuadros')

# Barriles e items (carpeta BARRILES): barril en 3 estados (entero, agrietado, roto), CD (puntos) y taco (vida).
# Escala para que el barril entero mida ~44 de alto en el mundo.
def prop_img(fname, world_h):
    im = Image.open(os.path.join(ROOT, 'BARRILES', fname)).convert('RGBA'); im = im.crop(im.getbbox())
    k = world_h * 2 / im.height
    return uri(im.resize((max(1, round(im.width * k)), round(world_h * 2)), Image.LANCZOS))
bar_path = os.path.join(ROOT, 'BARRILES', 'barrel.png')
if os.path.exists(bar_path):
    a, cells = frame_masks(bar_path, 3)
    h0 = np.nonzero(cells[0].any(1))[0]; k = 44 / (h0.max() - h0.min())       # alto del barril entero (34 + 30%)
    frs = cut(bar_path, 3, True, k * 2)
    sheet, pos = pack(frs)
    data['props'] = {'img': uri(sheet), 'barrel': [dict(x=pos[i][0], y=pos[i][1], w=f[0].width, h=f[0].height, ax=round(f[1], 1), ay=f[2])
                                                   for i, f in enumerate(frs)],
                     'cd': prop_img('cd.png', 32), 'taco': prop_img('taco health.png', 28)}  # +50%
    print('barriles: 3 estados + cd + taco')

# Musica (carpeta MUSICA): solo los primeros 30 s de cada tema, con fade out al final.
# Se decodifica y recodifica con afconvert (macOS) y se guarda en JUEGO/.music para no repetir el trabajo.
import subprocess, tempfile, wave
MUSIC_SECS, FADE_IN, FADE_OUT = 30, .15, 4.0
MUSIC_RMS_DB = -16.0   # todos los temas se llevan a este volumen promedio (dBFS), con limitador suave en los picos
MUSIC_VERSION = 'norm3'
def music_clip(src):
    os.makedirs(os.path.join(HERE, '.music'), exist_ok=True)
    out = os.path.join(HERE, '.music', os.path.basename(src).split('.mp3')[0].split('.wav')[0] + f'.{MUSIC_VERSION}.m4a')
    if not os.path.exists(out) or os.path.getmtime(out) < os.path.getmtime(src):
        with tempfile.TemporaryDirectory() as td:
            full, cut_ = os.path.join(td, 'full.wav'), os.path.join(td, 'cut.wav')
            subprocess.run(['afconvert', '-f', 'WAVE', '-d', 'LEI16', src, full], check=True)
            w = wave.open(full); ch, sr = w.getnchannels(), w.getframerate()
            n = min(w.getnframes(), int(MUSIC_SECS * sr))
            a = np.frombuffer(w.readframes(n), dtype=np.int16).reshape(-1, ch).astype(np.float32); w.close()
            env = np.ones(len(a), np.float32)
            fi, fo = int(FADE_IN * sr), int(FADE_OUT * sr)
            env[:fi] = np.linspace(0, 1, fi); env[-fo:] = np.linspace(1, 0, fo) ** 2
            # normalizar: mismo volumen promedio (RMS de la parte sin fades) para todos los temas
            x = a / 32768.0
            mid = x[int(1 * sr):int((MUSIC_SECS - FADE_OUT) * sr)]
            rms_db = 20 * np.log10(np.sqrt((mid ** 2).mean()) + 1e-9)
            x = x * 10 ** ((MUSIC_RMS_DB - rms_db) / 20)
            # limitador suave: lo que pase de 0.7 se comprime hacia 0.89 (-1 dB), margen para la compresion AAC
            ax = np.abs(x); over = ax > .7
            x[over] = np.sign(x[over]) * (.7 + .19 * np.tanh((ax[over] - .7) / .19))
            x = x * env[:, None]
            print(f'    {os.path.basename(src)[:40]:40s} volumen {rms_db:6.1f} dB -> {MUSIC_RMS_DB} dB')
            a = np.clip(x * 32767, -32768, 32767).astype(np.int16)
            o = wave.open(cut_, 'wb'); o.setnchannels(ch); o.setsampwidth(2); o.setframerate(sr); o.writeframes(a.tobytes()); o.close()
            subprocess.run(['afconvert', '-f', 'm4af', '-d', 'aac', '-b', '96000', cut_, out], check=True)
    return 'data:audio/mp4;base64,' + base64.b64encode(open(out, 'rb').read()).decode()
mdir = os.path.join(ROOT, 'MUSICA')
if os.path.isdir(mdir):
    songs = sorted(f for f in os.listdir(mdir) if f.lower().endswith(('.mp3', '.wav')))
    # nombres numerados (1.wav...): 1 = inicio, 2 = jefe, 3 = final; si no, se reconocen por el nombre
    num = {f.split('.')[0]: f for f in songs if f.split('.')[0].isdigit()}
    pick = lambda key: next((f for f in songs if key in f.lower()), None) if not num else num.get({'age': '1', 'carousel': '2', 'carusel': '2', 'dammit': '3', 'damit': '3'}.get(key, ''))
    title_s, boss_s = pick('age'), pick('carousel') or pick('carusel')
    game_s = [f for f in songs if f not in (title_s, boss_s)]
    final_s = pick('dammit') or pick('damit')   # tema de la animacion final
    data['music'] = {'title': music_clip(os.path.join(mdir, title_s)) if title_s else None,
                     'final': music_clip(os.path.join(mdir, final_s)) if final_s else None,
                     'boss': music_clip(os.path.join(mdir, boss_s)) if boss_s else None,
                     'game': [music_clip(os.path.join(mdir, f)) for f in game_s]}
    print('musica: inicio =', title_s, '| jefe =', boss_s, '| partida =', len(game_s), 'temas')

# Animacion final (carpeta FINAL): la banda tocando en el escenario, en loop.
# Orden: base, segundo fotograma, pausa antes del golpe, pleno concierto.
fdir = os.path.join(ROOT, 'FINAL')
if os.path.isdir(fdir):
    ff = [f for f in os.listdir(fdir) if f.lower().endswith('.png')]
    order = ['concierto punk', 'segundo fotograma', 'pausa antes', 'pleno concierto']
    ff.sort(key=lambda f: next((i for i, k in enumerate(order) if k in f.lower()), 99))
    data['final'] = [uri_jpg(Image.open(os.path.join(fdir, f)).convert('RGB').resize((1280, 720), Image.LANCZOS), 86) for f in ff]
    print('final:', len(ff), 'cuadros ->', ', '.join(ff))

logos = []
# logo: dos cuadros (ojos abiertos, ojos cerrados) en LOGOS/; si estan 1.png y 2.png se usan esos
# logo: ojos abiertos y ojos cerrados (carpeta LOGOS)
logo_files = ['Conejo pixelado salta en el logo Blink-2.png', 'Conejito Blink, parpadeo suave-1.png']
for f in logo_files:
    im = Image.open(os.path.join(ROOT, 'LOGOS', f)).convert('RGBA')
    logos.append(uri(im.resize((520, round(520 * im.height / im.width)), Image.LANCZOS)))
data['logo'] = logos

tpl = open(os.path.join(HERE, 'game_template.html'), encoding='utf-8').read()
html = tpl.replace('/*__ASSETS__*/null', json.dumps(data))
open(os.path.join(HERE, 'index.html'), 'w', encoding='utf-8').write(html)
print('index.html', round(len(html) / 1e6, 2), 'MB')
