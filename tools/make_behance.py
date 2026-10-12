# Arma el paquete de Behance a partir de los cuadros capturados del juego real
# (BEHANCE/cuadros-juego/<escena>/NNNN.jpg, a 1920x1080) y del arte original.
# Uso: python3 tools/make_behance.py
import glob, os, subprocess, sys
import numpy as np
import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
GAME = os.path.abspath(os.path.join(HERE, '..'))
ROOT = os.path.abspath(os.path.join(GAME, '..'))
OUT = os.path.join(ROOT, os.environ.get('BEHANCE_DIR', 'BEHANCE'))   # carpeta de salida (BEHANCE_DIR=BEHANCE_2 ...)
CAPS = os.path.join(OUT, 'cuadros-juego')
FONT = os.path.join(HERE, 'fonts', 'PressStart2P-Regular.ttf')
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
sys.path.insert(0, GAME)
GOLD, PINK, WHITE, INK = (255, 210, 79), (255, 79, 163), (242, 242, 242), (10, 10, 10)

def font(s): return ImageFont.truetype(FONT, s)
def rgba(p): return Image.open(p).convert('RGBA')
def caps(scene, a=0, b=None): return [Image.open(f).convert('RGB') for f in sorted(glob.glob(os.path.join(CAPS, scene, '*.jpg')))[a:b]]
def sub(*p): d = os.path.join(OUT, *p); os.makedirs(d, exist_ok=True); return d

def text(img, s, xy, size, fill=WHITE, anchor='mm', stroke=None):
    d = ImageDraw.Draw(img)
    d.text(xy, s, font=font(size), fill=fill, anchor=anchor, stroke_width=stroke if stroke is not None else max(2, size // 8), stroke_fill=INK)

def save_gif(frames, path, ms=90, colors=192, width=None):
    if width: frames = [f.resize((width, round(f.height * width / f.width)), Image.LANCZOS) for f in frames]
    # una paleta comun para todos los cuadros (sacada de una muestra) evita parpadeos de color
    sample = Image.new('RGB', (frames[0].width, frames[0].height * 4))
    for i, k in enumerate(np.linspace(0, len(frames) - 1, 4).astype(int)): sample.paste(frames[k].convert('RGB'), (0, i * frames[0].height))
    pal = sample.quantize(colors, method=Image.Quantize.MEDIANCUT)
    q = [f.convert('RGB').quantize(palette=pal, dither=Image.Dither.NONE) for f in frames]
    q[0].save(path, save_all=True, append_images=q[1:], duration=ms, loop=0, optimize=True, disposal=1)
    print(f'  {os.path.relpath(path, ROOT)}  {len(frames)} cuadros  {os.path.getsize(path) / 1e6:.1f} MB')

# ---------------------------------------------------------------- sprites desde los atlas del juego
def load_assets():
    import json, base64, io
    s = open(os.path.join(GAME, 'index.html'), encoding='utf-8').read()
    A = json.loads(s[s.index('const ASSETS=') + 13:s.index(';\nconst cv=')])
    dec = lambda u: Image.open(io.BytesIO(base64.b64decode(u.split(',', 1)[1]))).convert('RGBA')
    return A, dec
A, dec = load_assets()
ATLAS = {}
def sprite(kind, cid, anim, i=0):
    """Cuadro de una animacion a resolucion completa del atlas (los enemigos miran a la izquierda)."""
    c = A[kind][cid]
    if (kind, cid) not in ATLAS: ATLAS[(kind, cid)] = dec(c['img'])
    f = c['anims'][anim][i % len(c['anims'][anim])]
    return ATLAS[(kind, cid)].crop((f['x'], f['y'], f['x'] + f['w'], f['y'] + f['h'])), f['ax'], f['ay'], c.get('res', 2)

def place(img, spr, x, feet, h, flip=False, shadow=True):
    im, ax, ay, _ = spr
    k = h / im.height; im = im.resize((max(1, round(im.width * k)), h), Image.LANCZOS); ax *= k
    if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT); ax = im.width - ax
    if shadow:
        sh = Image.new('RGBA', img.size, (0, 0, 0, 0)); w = im.width * .55
        ImageDraw.Draw(sh).ellipse((x - w / 2, feet - h * .035, x + w / 2, feet + h * .035), fill=(0, 0, 0, 120))
        img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(h * .02)))
    img.alpha_composite(im, (round(x - ax), round(feet - im.height)))

HEROES = [('mark', 'MARK', 'BALANCED', 'PINK BASS'), ('tom', 'TOM', 'SLOW BUT HEAVY', 'SEAFOAM GUITAR'), ('travis', 'TRAVIS', 'FAST BUT LIGHT', 'DRUMSTICKS')]
FOES = [('darkness', 'DARKNESS'), ('hardman', 'HARDMAN'), ('juggalo', 'JUGGALO'), ('mortalcore', 'MORTALCORE'), ('punx', 'PUNX'),
        ('screamguy', 'SCREAM GUY'), ('skinman', 'SKIN MAN'), ('trashrat', 'TRASH RAT'), ('warrior', 'WARRIOR')]
LOGO = dec(A['logo'][0]); LOGO2 = dec(A['logo'][1])

def stage_bg(w, h, cam=900):
    """Fondo del festival armado con las capas del juego (cielo, nubes, palmeras, publico, suelo, carpas)."""
    W, H = 480, 270; k = w / W
    img = Image.new('RGBA', (w, h), (36, 152, 253, 255))
    def tile(L, vx):
        im = dec(L['img']); lw, lh = im.width / 2 * k, im.height / 2 * k
        im = im.resize((round(lw), round(lh)), Image.LANCZOS)
        off = vx * L['f'] * k; n = int(off // lw); x = n * lw - off
        while x < w:
            t = im.transpose(Image.FLIP_LEFT_RIGHT) if L.get('mirror') and n % 2 else im
            img.alpha_composite(t, (round(x), round(L['y'] * k))); x += lw; n += 1
    for L in A['bg']['layers']: tile(L, cam)
    near = [dec(u) for u in A['bg']['near']]; nw = near[0].width / 2
    for i, im in enumerate(near):
        x = (i * nw - cam) * k
        if x > w or x + im.width / 2 * k < 0: continue
        img.alpha_composite(im.resize((round(im.width / 2 * k), round(im.height / 2 * k)), Image.LANCZOS), (round(x), round(A['bg']['nearY'] * k)))
    return img

# ---------------------------------------------------------------- piezas
def titulos():
    d = sub('titulos')
    for name, label in [('the-characters', 'THE CHARACTERS'), ('the-enemies', 'THE ENEMIES'), ('the-stages', 'THE STAGES'), ('the-boss', 'THE BOSS'), ('the-fights', 'THE FIGHTS')]:
        f = font(96); w = int(f.getlength(label)) + 80
        img = Image.new('RGBA', (w, 170), (0, 0, 0, 0)); dr = ImageDraw.Draw(img)
        dr.text((w / 2 + 8, 92), label, font=f, fill=PINK, anchor='mm', stroke_width=10, stroke_fill=INK)
        dr.text((w / 2, 84), label, font=f, fill=GOLD, anchor='mm', stroke_width=10, stroke_fill=INK)
        img.save(os.path.join(d, name + '-transparente.png')); print('  titulos/' + name + '-transparente.png')

def logos():
    d = sub('logos')
    LOGO.save(os.path.join(d, 'logo.png')); LOGO2.save(os.path.join(d, 'logo-parpadeo.png'))
    save_gif([LOGO if (i % 12) < 8 else LOGO2 for i in range(24)], os.path.join(d, 'logo-animado.gif'), ms=80, width=520)

def fondos():
    d = sub('fondos'); W, H = 1920, 1080
    for i, cam in enumerate([120, 1350, 2600, 3800, 5150, 6380]):
        stage_bg(W, H, cam).convert('RGB').save(os.path.join(d, f'zona-{i + 1}-16x9.png'), optimize=True)
    # panoramico: todo el recorrido de la capa cercana con el cielo detras
    near = [dec(u) for u in A['bg']['near']]
    tot = sum(im.width for im in near); h = near[0].height
    pano = Image.new('RGBA', (tot, h), (36, 152, 253, 255)); x = 0
    for im in near: pano.alpha_composite(im, (x, 0)); x += im.width
    pano = pano.resize((round(pano.width * 900 / pano.height), 900), Image.LANCZOS)
    for k in range(3):
        c = pano.crop((k * pano.width // 3, 0, (k + 1) * pano.width // 3, 900))
        c.convert('RGB').save(os.path.join(d, f'recorrido-panoramico-{k + 1}.png'), optimize=True)
    print('  fondos: 6 zonas 16:9 + recorrido panoramico en 3 partes')

def personajes():
    d = sub('gifs')
    seq = {'mark': ['idle', 'walk', 'jab', 'cross', 'kick', 'jump', 'airkick', 'special'],
           'tom': ['idle', 'walk', 'jab', 'cross', 'kick', 'jump', 'airkick', 'special'],
           'travis': ['idle', 'walk', 'jab', 'cross', 'kick', 'jump', 'airkick', 'special']}
    bg = stage_bg(1080, 1080 * 9 // 16, 2600).crop((240, 0, 840, 607)).resize((1080, 1080), Image.LANCZOS)
    for cid, name, tag, sp in HEROES:
        frames = []
        for an in seq[cid]:
            n = len(A['chars'][cid]['anims'][an])
            for i in range(n * (3 if an in ('idle', 'walk') else 2)):
                img = bg.copy(); img.alpha_composite(Image.new('RGBA', img.size, (0, 0, 0, 90)))
                place(img, sprite('chars', cid, an, i), 540, 930, 620)
                text(img, name, (540, 120), 64, GOLD); text(img, an.upper(), (540, 1010), 28)
                frames.append(img.convert('RGB'))
        save_gif(frames, os.path.join(d, f'personaje-{cid}.gif'), ms=110, width=540)
    for cid, name in FOES:
        frames = []
        for an in ['walk', 'punch', 'kick', 'jump', 'fall', 'getup']:
            n = len(A['enemies'][cid]['anims'][an])
            for i in range(n * 2):
                img = bg.copy(); img.alpha_composite(Image.new('RGBA', img.size, (0, 0, 0, 90)))
                place(img, sprite('enemies', cid, an, i), 540, 930, 600 if an not in ('fall', 'getup') else 520, flip=True)
                text(img, name, (540, 120), 56, PINK); text(img, an.upper(), (540, 1010), 28)
                frames.append(img.convert('RGB'))
        save_gif(frames, os.path.join(d, f'enemigo-{cid}.gif'), ms=120, width=540)
    frames = []
    for an in ['idle', 'walk', 'punch', 'kick', 'guitar', 'fall', 'getup']:
        n = len(A['enemies']['villain']['anims'][an])
        for i in range(n * 2):
            img = bg.copy(); img.alpha_composite(Image.new('RGBA', img.size, (40, 0, 20, 120)))
            place(img, sprite('enemies', 'villain', an, i), 540, 950, 700, flip=True)
            text(img, 'BOX CAR TOM', (540, 110), 56, PINK); text(img, an.upper(), (540, 1020), 28)
            frames.append(img.convert('RGB'))
    save_gif(frames, os.path.join(d, 'jefe-box-car-tom.gif'), ms=120, width=540)

def poster():
    """Poster vertical: logo arriba, BOX CAR TOM en el escenario, enemigos a los lados y los 3 heroes al frente."""
    W, H = 1080, 1920
    img = stage_bg(3413, 1920, 6420).crop((1180, 0, 1180 + W, H))
    img.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 60)))
    grad = Image.new('L', (1, 900)); [grad.putpixel((0, y), int(225 * (y / 899) ** 1.3)) for y in range(900)]
    img.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, 900), 0)] * 3 + [grad.resize((W, 900))]), (0, H - 900))
    top = Image.new('L', (1, 520)); [top.putpixel((0, y), int(170 * (1 - y / 519) ** 1.5)) for y in range(520)]
    img.alpha_composite(Image.merge('RGBA', [Image.new('L', (W, 520), 0)] * 3 + [top.resize((W, 520))]), (0, 0))
    lg = LOGO.resize((820, round(LOGO.height * 820 / LOGO.width)), Image.LANCZOS)
    img.alpha_composite(lg, ((W - lg.width) // 2, 70))
    # fila de atras: enemigos; centro: el jefe; frente: heroes
    for (cid, _), x in zip(FOES[:6], (95, 255, 415, 665, 825, 985)):
        place(img, sprite('enemies', cid, 'punch'), x, 1330, 300, flip=x > 540)
    place(img, sprite('enemies', 'villain', 'idle'), 540, 1400, 520, flip=True)
    for (cid, *_), x in zip(HEROES, (215, 540, 865)):
        place(img, sprite('chars', cid, 'idle'), x, 1720, 440, flip=x > 540)
    text(img, 'MARK  TOM  TRAVIS', (540, 1790), 36, GOLD)
    text(img, 'VS BOX CAR TOM', (540, 1850), 30, PINK)
    img.convert('RGB').save(os.path.join(OUT, 'poster-personajes-9x16.png'), optimize=True)
    print('  poster-personajes-9x16.png')

# GIFs de escenas capturadas: 800 px y ~10 cuadros por segundo, para quedar bajo el limite de Behance (~20 MB)
def scene_gif(scene, path, step=3, ms=100, width=800, colors=160, a=0, b=None):
    fr = caps(scene, a, b)
    if fr: save_gif(fr[::step], path, ms=ms, width=width, colors=colors)

def peleas():
    d = sub('gifs')
    for scene, label in [('fight1', 'pelea-1-mark'), ('fight2', 'pelea-2-tom'), ('fight3', 'pelea-3-travis')]:
        scene_gif(scene, os.path.join(d, label + '.gif'))
    scene_gif('boss', os.path.join(d, 'pelea-jefe-box-car-tom.gif'), step=4)
    scene_gif('select', os.path.join(d, 'seleccion.gif'))
    scene_gif('title', os.path.join(d, 'intro.gif'), step=4)
    scene_gif('final', os.path.join(d, 'final-banda.gif'), step=1, ms=140, width=960)

def save_gif_hq(frames, path, ms, width, focus=(0.25, 0.08, 0.75, 0.95)):
    """GIF de alta fidelidad: paleta propia de 256 colores por cuadro, reforzando la zona 'focus'
    (logo y textos) para que sus colores no se pierdan frente al fondo."""
    out = []
    for f in frames:
        f = f.resize((width, round(f.height * width / f.width)), Image.LANCZOS).convert('RGB')
        x0, y0, x1, y1 = [round(v * s) for v, s in zip(focus, (f.width, f.height, f.width, f.height))]
        c = f.crop((x0, y0, x1, y1))
        samp = Image.new('RGB', (f.width, f.height + c.height * 3)); samp.paste(f, (0, 0))
        for k in range(3): samp.paste(c, (0, f.height + k * c.height))
        pal = samp.quantize(256, method=Image.Quantize.MEDIANCUT)
        out.append(f.quantize(palette=pal, dither=Image.Dither.NONE))
    out[0].save(path, save_all=True, append_images=out[1:], duration=ms, loop=0, optimize=True, disposal=1)
    print(f'  {os.path.relpath(path, ROOT)}  {len(out)} cuadros  {os.path.getsize(path) / 1e6:.1f} MB')

def intro_gif():
    save_gif_hq(caps('title')[::6], os.path.join(OUT, 'intro-1400.gif'), ms=150, width=1400)

def banda():
    d = sub('banda'); src = os.path.join(ROOT, 'FINAL')
    order = ['concierto punk', 'segundo fotograma', 'pausa antes', 'pleno concierto']
    ff = sorted([f for f in os.listdir(src) if f.lower().endswith('.png')], key=lambda f: next((i for i, k in enumerate(order) if k in f.lower()), 99))
    imgs = [Image.open(os.path.join(src, f)).convert('RGB') for f in ff]
    save_gif(imgs * 3, os.path.join(d, 'banda-en-vivo.gif'), ms=140, width=1280, colors=224)
    imgs[3].save(os.path.join(d, 'banda-en-vivo.png'), optimize=True); print('  banda/banda-en-vivo.png')

def heroes_16x9():
    """Por heroe, dos GIF 16:9 (1280x720): todas sus animaciones a la vez en una grilla, y una por una."""
    d = sub('gifs', 'heroes-16x9'); W, H = 1280, 720
    bg = stage_bg(W, H, 2600); bg.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 130)))
    names = {'idle': 'GUARD', 'walk': 'WALK', 'jab': 'JAB', 'cross': 'CROSS', 'kick': 'KICK', 'jump': 'JUMP',
             'airkick': 'FLYING KICK', 'special': 'SPECIAL', 'hurt': 'HIT', 'fall': 'FALL', 'getup': 'GET UP', 'defeat': 'DEFEAT'}
    order = ['idle', 'walk', 'jab', 'cross', 'kick', 'jump', 'airkick', 'special', 'hurt', 'fall', 'getup', 'defeat']
    def put(img, spr, x, feet, k):
        im, ax, ay, _ = spr
        im = im.resize((max(1, round(im.width * k)), max(1, round(im.height * k))), Image.LANCZOS)
        img.alpha_composite(im, (round(x - ax * k), round(feet - im.height)))
    for cid, name, tag, sp in HEROES:
        an = A['chars'][cid]['anims']; ref = an['idle'][0]['h']
        # grilla 4x3 con las 12 animaciones al mismo tiempo
        k = 140 / ref; frames = []
        for t in range(24):
            img = bg.copy(); img.alpha_composite(Image.new('RGBA', (W, H), (0, 0, 0, 60))); text(img, name + '  -  ALL MOVES', (W // 2, 34), 26, GOLD)
            for i, a in enumerate(order):
                cx, top = 160 + (i % 4) * 320, 70 + (i // 4) * 215
                n = len(an[a]); put(img, sprite('chars', cid, a, t % n), cx, top + 172, k)
                text(img, names[a], (cx, top + 192), 14, PINK)
            frames.append(img.convert('RGB'))
        save_gif(frames, os.path.join(d, f'{cid}-todas-las-animaciones.gif'), ms=150, colors=200)
        # una animacion por vez, grande
        k = 470 / ref; frames = []
        for a in order:
            n = len(an[a])
            for t in range(n * (3 if a in ('idle', 'walk') else 2)):
                img = bg.copy(); put(img, sprite('chars', cid, a, t), W // 2, 640, k)
                text(img, name, (W // 2, 50), 40, GOLD); text(img, names[a], (W // 2, 690), 24, PINK)
                frames.append(img.convert('RGB'))
        save_gif(frames, os.path.join(d, f'{cid}-movimientos.gif'), ms=130, colors=200)

# ---------------------------------------------------------------- reels
def music_clip():
    m = sorted(glob.glob(os.path.join(GAME, '.music', '*.m4a')))
    pick = next((p for p in m if os.path.basename(p).startswith('3.')), None) or (m[0] if m else None)
    return pick

def write_video(frames_iter, n, path, w, h, fps=25):
    audio = music_clip()
    cmd = [FFMPEG, '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{w}x{h}', '-r', str(fps), '-i', '-']
    if audio: cmd += ['-i', audio, '-map', '0:v', '-map', '1:a', '-c:a', 'aac', '-b:a', '160k', '-shortest']
    cmd += ['-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-crf', '19', '-preset', 'medium', '-movflags', '+faststart', path]
    p = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    for f in frames_iter: p.stdin.write(f.convert('RGB').tobytes())
    p.stdin.close(); p.wait()
    print(f'  {os.path.relpath(path, ROOT)}  {n / fps:.0f} s  {os.path.getsize(path) / 1e6:.1f} MB')

def reel_plan():
    """Secuencia de 30 s a 25 fps: (escena, cuadros, titulo). Los cuadros capturados son a ~30 fps de juego."""
    return [('credit', 45, None), ('title', 50, None), ('select', 55, 'CHOOSE YOUR FIGHTER'), ('fight1', 120, 'MARK'), ('fight2', 120, 'TOM'),
            ('fight3', 110, 'TRAVIS'), ('boss', 150, 'VS BOX CAR TOM'), ('final', 100, None)]   # el final ya trae su texto

def reel_frames(fmt):
    W, H = (1920, 1080) if fmt == '16x9' else (1080, 1920)
    plan = reel_plan(); total = sum(p[1] for p in plan)
    for scene, n, title in plan:
        src = caps(scene)
        if not src: continue
        for i in range(n):
            f = src[min(len(src) - 1, int(i * len(src) / n))]
            if fmt == '16x9':
                img = f.copy().convert('RGBA')
            else:
                img = Image.new('RGBA', (W, H), INK + (255,))
                lg = LOGO.resize((384, round(LOGO.height * 384 / LOGO.width)), Image.LANCZOS)   # 40% mas chico
                img.alpha_composite(lg, ((W - lg.width) // 2, 260))
                # el cuadro completo del juego (16:9) a todo el ancho, sin recortes: se ve toda la accion
                g = f.resize((1080, 608), Image.LANCZOS)
                img.alpha_composite(g.convert('RGBA'), (0, 620))
            if title and 8 <= i < n - 4:
                a = min(1, (i - 8) / 6)
                layer = Image.new('RGBA', img.size, (0, 0, 0, 0))
                y = 120 if fmt == '16x9' else 1310
                text(layer, title, (W // 2, y), 54 if fmt == '16x9' else 46, GOLD)
                if a < 1: layer.putalpha(layer.getchannel('A').point(lambda v: int(v * a)))
                img.alpha_composite(layer)
            yield img
    return total

def reels():
    n = sum(p[1] for p in reel_plan())
    write_video(reel_frames('16x9'), n, os.path.join(OUT, 'reel-16x9.mp4'), 1920, 1080)
    write_video(reel_frames('9x16'), n, os.path.join(OUT, 'reel-9x16.mp4'), 1080, 1920)

if __name__ == '__main__':
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1:] or ['titulos', 'logos', 'fondos', 'poster', 'personajes', 'banda', 'peleas', 'intro_gif', 'reels']
    for w in what:
        print('>', w); globals()[w]()
