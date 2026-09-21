#!/usr/bin/env python3
"""LES ICÔNES d'AtomBox — engendrées, sans bibliothèque d'image (RM3294, RM3251, D172).

    python3 outils/icones.py        # réécrit icones/*.png

Le dessin est celui qu'on a arbitré au CDC (`docs/logos/`, RM2881) : un atome dont le noyau est un
**@** tracé d'UN SEUL TRAIT, de la goutte centrale jusqu'à l'électron bleu, qu'il dépasse pour
continuer en orbite. Les orbites sont en perspective — le brin proche est plus épais, plus opaque,
et il efface ce qui passe derrière —, chaque électron porte le halo de son canal.

Le dessin n'a AUCUN APLAT : ce qui passe devant se détache par une réserve qui épouse le trait et
*efface* (alpha à zéro), jamais par un fond peint. C'est ce qui permet au même dessin de servir sur
fond clair, sur fond sombre et dans le bleu plein de l'icône Android.

LES PROPORTIONS CHANGENT AVEC LA TAILLE (« optical sizing », cf. `REGLAGES`) : un logo qui garde
les siennes en rétrécissant devient gris. Sous 48 px le trait s'épaissit, l'ouverture du @ s'élargit,
la barre de rattachement maigrit puis disparaît, et sous 32 px les orbites s'effacent — le @ y
occupe tant de place que les ellipses croiseraient son anneau. Restent les électrons, leur halo, et
la queue, qui est elle-même un morceau d'orbite : le câblage survit jusqu'à 16 px.

Le cœur du dessin est RECOPIÉ de `docs/logos/arobase.py`, le banc d'essai où il a été mis au point
et où son journal de décisions est tenu. Recopié, pas importé : le CDC vit dans un autre dépôt, et
le produit ne doit pas dépendre de sa présence pour se construire. Toute retouche se fait au banc
d'abord, puis se reporte ici.

La variante « maskable » est celle qu'Android découpe à sa guise (cercle, carré arrondi, goutte) :
le dessin doit tenir dans le disque central de 80 %, et le fond couvrir tout le carré. Sans elle,
Android pose l'icône rétrécie sur un fond blanc.

La sortie est REPRODUCTIBLE : mêmes octets à chaque exécution (aucune date dans le PNG).
"""
from __future__ import annotations
import math
import os
import struct
import zlib

ICI = os.path.dirname(os.path.abspath(__file__))
SORTIE = os.path.join(ICI, "..", "icones")

VIDE = (0.0, 0.0, 0.0, 0.0)

# ── palettes ────────────────────────────────────────────────────────────────────────────────────
# `fond` ne sert qu'à aplatir l'icône d'application, qu'Android exige opaque. Le logo, lui, ne peint
# jamais le fond : sa réserve efface.
PALETTES = {
    "clair":  dict(accent=(0x2F, 0x6F, 0xED), vert=(0x0F, 0x7B, 0x4F), orange=(0xB4, 0x53, 0x09),
                   fond=(0xFF, 0xFF, 0xFF)),
    "sombre": dict(accent=(0x5B, 0x8D, 0xFF), vert=(0x3F, 0xBB, 0x85), orange=(0xD9, 0x9A, 0x3A),
                   fond=(0x14, 0x17, 0x1C)),
    # l'icône d'application : Android impose un fond plein, donc tout s'inverse — l'atome passe en
    # blanc sur le bleu de la marque.
    "icone":  dict(accent=(0xFF, 0xFF, 0xFF), vert=(0x5F, 0xE0, 0xA8), orange=(0xFF, 0xC4, 0x6B),
                   fond=(0x2F, 0x6F, 0xED)),
}

# ── réglages par taille (optical sizing) ────────────────────────────────────────────────────────
# Tout est en fraction du côté du carré.
#   R / trait  le rayon du @ et l'épaisseur de son trait (en fraction de R)
#   spire      de combien de degrés le bras intérieur prolonge l'anneau en plongeant vers le
#              centre. Il n'y a plus ni point ni barre : le @ est UNE SEULE SPIRALE d'épaisseur
#              constante, de la goutte centrale jusqu'à l'électron. Moins de spire = le bras
#              plonge plus vite, donc la contre-forme reste ouverte — c'est ce qu'il faut en petit.
#   goutte     le grossissement du bout du trait, là où la spirale s'arrête près du centre : c'est
#              lui qui fait la goutte. À 1.0, on aurait un bout de trait arrondi, et rien d'autre.
#   enfle      de combien de degrés l'enflement démarre AVANT la fin de l'anneau. À zéro, il tient
#              dans le seul bras intérieur — et c'est le bon réglage : rendu à 45° d'avance, le
#              trait arrive gras sur tout le dernier quart de l'anneau et mange la contre-forme.
#              Le paramètre reste, parce que c'est le genre de réglage qu'on veut pouvoir rouvrir.
#   ouv        le secteur où l'anneau est TRACÉ (le reste est son ouverture) ; son premier angle est
#              aussi celui où naît la queue
#   reserve    la marge d'effacement autour de ce qui passe devant. En fraction, donc elle grossit
#              quand on rapetisse : il lui faut environ un pixel, quelle que soit la taille.
#   a / b      les demi-axes des orbites. `b` est large : l'orbite doit passer au large du @ et de
#              sa réserve, sinon elle s'y fait manger.
#   orb/orb_a  épaisseur et opacité d'une orbite, avant l'effet de perspective
#   orbites    combien on en garde. ZÉRO sous 32 px : le @ y occupe tant de place que les ellipses
#              croiseraient son anneau. Restent les électrons, leur halo — et la queue, qui est
#              elle-même un morceau d'orbite, donc le câblage survit jusqu'à 16 px.
#   el / halo  le rayon d'un électron, et celui de son halo en multiples du précédent
REGLAGES = [
    (96, dict(reserve=.016, R=.185, trait=.28, spire=60, goutte=2.30, enfle=0, queue=1.0, a=.440, b=.245, el=.050, orb=.015, orb_a=.50, halo=3.0, halo_a=.28, orbites=3, arobase=True, ouv=(100, 20))),
    (64, dict(reserve=.020, R=.193, trait=.30, spire=60, goutte=2.30, enfle=0, queue=1.0, a=.434, b=.248, el=.054, orb=.018, orb_a=.52, halo=2.9, halo_a=.33, orbites=3, arobase=True, ouv=(100, 20))),
    (48, dict(reserve=.025, R=.205, trait=.32, spire=60, goutte=2.30, enfle=0, queue=1.0, a=.426, b=.262, el=.060, orb=.021, orb_a=.54, halo=2.8, halo_a=.40, orbites=3, arobase=True, ouv=(102, 16))),
    (32, dict(reserve=.032, R=.200, trait=.36, spire=58, goutte=2.35, enfle=0, queue=1.0, a=.414, b=.278, el=.070, orb=.027, orb_a=.58, halo=2.6, halo_a=.50, orbites=3, arobase=True, ouv=(105, 10))),
    (24, dict(reserve=.042, R=.245, trait=.40, spire=55, goutte=2.40, enfle=0, queue=1.0, a=.404, b=.240, el=.080, orb=.033, orb_a=.62, halo=2.5, halo_a=.60, orbites=0, arobase=True, ouv=(108, 352))),
    (16, dict(reserve=.052, R=.268, trait=.44, spire=52, goutte=2.45, enfle=0, queue=1.0, a=.392, b=.238, el=.092, orb=.040, orb_a=.66, halo=2.4, halo_a=.68, orbites=0, arobase=True, ouv=(110, 350))),
]


def reglages(taille):
    """le jeu de proportions taillé pour cette taille (le plus proche en dessous)"""
    choisi = REGLAGES[0][1]
    for t, r in REGLAGES:
        if taille <= t:
            choisi = r
    return choisi


# ── primitives ──────────────────────────────────────────────────────────────────────────────────
def dist_ellipse(rx, ry, a, b):
    """distance ~exacte du point à l'ellipse (a, b) centrée en 0 : F/|∇F|.

    L'approximation naïve `|hypot(rx/a, ry/b) - 1| * a` fait grossir le trait aux extrémités de
    l'ellipse — c'est-à-dire précisément là où se trouvent les électrons."""
    f = (rx / a) ** 2 + (ry / b) ** 2 - 1.0
    g = math.hypot(2 * rx / (a * a), 2 * ry / (b * b))
    return abs(f) / g if g else 9.9


def secteur(ang, a0, a1):
    """l'angle (degrés, 0 = droite, 90 = bas — y vers le bas) est-il dans [a0, a1] ?"""
    ang %= 360
    return (a0 % 360 <= ang <= a1 % 360) if a0 % 360 <= a1 % 360 else (ang >= a0 % 360 or ang <= a1 % 360)


def segment(px, py, ax, ay, bx, by, e):
    """le point est-il à moins de e/2 du segment [a, b] ?"""
    dx, dy = bx - ax, by - ay
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy)) <= e / 2


def melanger(dest, coul, alpha):
    """pose `coul` à `alpha` par-dessus `dest` (RGBA flottant, non prémultiplié)"""
    if alpha <= 0: return dest
    dr, dg, db, da = dest
    r, g, b = (v / 255.0 for v in coul)
    na = alpha + da * (1 - alpha)
    if na <= 0: return VIDE
    k = da * (1 - alpha)
    return ((r * alpha + dr * k) / na, (g * alpha + dg * k) / na, (b * alpha + db * k) / na, na)


def poser(dessous, dessus):
    """compose deux RGBA — sert à remettre les halos SOUS le trait, après coup.

    Les halos ne peuvent pas être peints en premier sur la même couche : les réserves les
    perceraient, et l'on verrait une entaille dans chaque lueur."""
    r, g, b, al = dessus
    if al >= 1 or al <= 0: return dessus if al >= 1 else dessous
    return melanger(dessous, (r * 255, g * 255, b * 255), al)


_BRAS = {}


def bras(reg, fin_anneau):
    """le bras intérieur, échantillonné en capsules : (x, y, demi-épaisseur).

    Pourquoi ne pas le tester comme l'anneau, par `|d - rayon(φ)| <= e/2` ? Parce que cette mesure
    est RADIALE, et qu'un trait se mesure PERPENDICULAIREMENT à sa courbe. Sur l'anneau le rayon est
    constant, les deux coïncident. Sur le bras, qui plonge de 0,92 R à 0,06 R en un sixième de tour,
    elles divergent brutalement : le trait n'y faisait plus que 18 à 26 % de son épaisseur au plus
    fort du virage — c'est exactement l'amincissement qu'on voyait. Une polyligne de capsules donne
    la vraie largeur, et ses bouts arrondis font la goutte sans qu'on ait à poser un disque dessus.

    Échantillonné une fois par jeu de réglages, pas par pixel : 28 segments suffisent à cette
    longueur, et le test est borné au disque du @."""
    cle = (reg["R"], reg["trait"], reg["spire"], reg["goutte"], fin_anneau)
    if cle not in _BRAS:
        R, e, N = reg["R"], reg["R"] * reg["trait"], 28
        pts = []
        for i in range(N + 1):
            u = i / N
            phi = math.radians(fin_anneau + u * reg["spire"])
            r = R * (.92 + (.06 - .92) * u * u * (3 - 2 * u))
            # le trait enfle en u² : imperceptible au départ, pleine goutte à l'arrivée
            pts.append((r * math.cos(phi), r * math.sin(phi),
                        e * (1 + (reg["goutte"] - 1) * u * u) / 2))
        _BRAS[cle] = pts
    return _BRAS[cle]


# ── le dessin ───────────────────────────────────────────────────────────────────────────────────
def pixel(x, y, reg, pal, variante="rond"):
    """couleur du point (x, y) du carré unité, en RGBA flottant sur fond transparent"""
    dx, dy = x - .5, y - .5
    a, b, m = reg["a"], reg["b"], reg["reserve"]
    accent = pal["accent"]
    electrons = ((0, pal["accent"]), (120, pal["vert"]), (240, pal["orange"]))

    # ── les halos, sur leur propre couche (voir `poser`) ────────────────────────────────────────
    lueur = VIDE
    for ang, coul in electrons:
        t = math.radians(ang)
        d = math.hypot(x - (.5 + a * math.cos(t)), y - (.5 + a * math.sin(t)))
        re, rh = reg["el"], reg["el"] * reg["halo"]
        if re < d <= rh:
            lueur = melanger(lueur, coul, ((1 - (d - re) / (rh - re)) ** 2) * reg["halo_a"])

    out = VIDE
    R, e = reg["R"], reg["R"] * reg["trait"]
    d0 = math.hypot(dx, dy)
    th = math.degrees(math.atan2(dy, dx))
    depart = reg["ouv"][0]                       # l'angle où l'anneau s'arrête : la queue y naît

    # ── la queue ────────────────────────────────────────────────────────────────────────────────
    # Son rayon quitte l'anneau tout de suite (sinon elle le longe et l'on lit une spirale), mais
    # son épaisseur et son opacité tiennent jusqu'aux deux tiers du trajet, puis rejoignent celles
    # de l'orbite. Elle continue au-delà de l'électron, où elle EST l'orbite.
    queue_r, queue_ep, queue_al = None, 0.0, 0.0
    if reg["arobase"] and -35 <= th <= depart:
        w = max(0.0, min(1.0, 1 - th / depart))
        w = w * w * (3 - 2 * w)                              # adouci : pas d'angle au décollage
        tr = math.radians(th)
        r_orbite = a * b / math.hypot(b * math.cos(tr), a * math.sin(tr))
        queue_r = R * .92 + (r_orbite - R * .92) * w
        v = max(0.0, min(1.0, (w - .40) / .60))
        v = v * v * (3 - 2 * v)
        proche = max(0.0, min(1.0, (dy / b + 1) / 2))
        al_orb = min(.92, reg["orb_a"] * (.70 + .60 * proche))
        gros = e * reg["queue"]
        queue_ep = gros + (reg["orb"] - gros) * v
        queue_al = 1.0 + (al_orb - 1.0) * v

    def sur_queue(marge=0.0):
        return queue_r is not None and abs(d0 - queue_r) <= queue_ep / 2 + marge

    # ── la spirale : l'anneau, puis le bras qui plonge vers le centre ───────────────────────────
    # Un seul trait, d'épaisseur constante, parcouru par l'angle φ : la queue de −35° au départ de
    # l'anneau, l'anneau jusqu'à son autre bout, puis le bras intérieur qui plonge d'un quart de
    # tour de plus et s'arrête en goutte près du centre. Le rayon ne fait que décroître le long de
    # φ : c'est donc bien une spirale continue, de l'électron jusqu'au cœur.
    #
    # Le bras naît dans l'OUVERTURE de l'anneau, pas sous lui : le temps qu'il revienne passer
    # dessous, il s'en est assez écarté pour que la contre-forme — ce mince blanc entre les deux
    # tours — reste ouverte. C'est elle qui porte la lecture du @.
    fin_anneau = reg["ouv"][1] + (360 if reg["ouv"][1] < depart else 0)

    def sur_anneau(marge):
        """l'anneau : rayon constant, donc la mesure radiale y est exacte"""
        for k in (-1, 0, 1, 2):
            phi = th + 360 * k
            if depart <= phi <= fin_anneau and abs(d0 - R * .92) <= e / 2 + marge:
                return True
        return False

    def sur_bras(marge):
        """le bras et sa goutte — distance à une polyligne de capsules (voir `bras`)"""
        if d0 > R * 1.05 + marge: return False
        pts = bras(reg, fin_anneau)
        for i in range(len(pts) - 1):
            ax, ay, ra = pts[i]
            bx, by, rb = pts[i + 1]
            ux, uy = bx - ax, by - ay
            l2 = ux * ux + uy * uy
            t = 0.0 if l2 == 0 else max(0.0, min(1.0, ((dx - ax) * ux + (dy - ay) * uy) / l2))
            if math.hypot(dx - (ax + t * ux), dy - (ay + t * uy)) <= ra + (rb - ra) * t + marge:
                return True
        return False

    def encre(marge):
        """la spirale ET sa queue — un seul geste, donc une seule réserve.

        Les traiter séparément creuserait un vide à l'endroit précis où ils se rejoignent."""
        return sur_anneau(marge) or sur_bras(marge) or sur_queue(marge)

    # ── les orbites, triées par profondeur AU POINT COURANT ─────────────────────────────────────
    # Une orbite est un cercle vu de biais : son brin proche passe devant, le lointain derrière. On
    # trie donc par profondeur ici même, et chaque brin efface ce qui est derrière lui avant de se
    # poser : c'est ce qui rend les croisements lisibles.
    brins = []
    for k, rot in enumerate((0, 60, 120)):
        if k >= reg["orbites"]: break
        t = math.radians(rot)
        rx = dx * math.cos(t) + dy * math.sin(t)
        ry = -dx * math.sin(t) + dy * math.cos(t)
        proche = max(0.0, min(1.0, (ry / b + 1) / 2))        # 0 au plus loin, 1 au plus près
        brins.append((proche, dist_ellipse(rx, ry, a, b),
                      reg["orb"] * (.78 + .44 * proche),
                      min(.92, reg["orb_a"] * (.70 + .60 * proche))))
    for _proche, dist, ep, al in sorted(brins):
        if dist <= ep / 2 + m: out = VIDE                    # la réserve efface, elle ne peint pas
        if dist <= ep / 2: out = melanger(out, accent, al)

    # ── le @ et sa queue, par-dessus les orbites ────────────────────────────────────────────────
    if reg["arobase"]:
        if encre(m): out = VIDE
        if sur_queue(): out = melanger(out, accent, queue_al)
        elif encre(0.0): out = melanger(out, accent, 1.0)

    # ── les électrons, par-dessus tout : ce sont eux qu'on voit en premier ───────────────────────
    for ang, coul in electrons:
        t = math.radians(ang)
        if math.hypot(x - (.5 + a * math.cos(t)), y - (.5 + a * math.sin(t))) <= reg["el"]:
            out = melanger(out, coul, 1.0)

    return poser(lueur, out)


def dessiner(taille, variante="rond", palette="clair", n=4):
    """le logo en `taille`×`taille`, RGBA, avec les proportions taillées pour cette taille"""
    return _rendre(taille, reglages(taille), PALETTES[palette], variante, n)


def _rendre(taille, reg, pal, variante="rond", n=4):
    """le même, avec des réglages imposés — sert aux planches de comparaison"""
    img = []
    for j in range(taille):
        ligne = []
        for i in range(taille):
            sr = sg = sb = sa = 0.0
            for sj in range(n):
                for si in range(n):
                    r, g, b, al = pixel((i + (si + .5) / n) / taille,
                                        (j + (sj + .5) / n) / taille, reg, pal, variante)
                    sr += r * al; sg += g * al; sb += b * al; sa += al
            ligne.append((sr / sa, sg / sa, sb / sa, sa / (n * n)) if sa > 0 else VIDE)
        img.append(ligne)
    return img


# ── sortie PNG ──────────────────────────────────────────────────────────────────────────────────


# ── sortie PNG ──────────────────────────────────────────────────────────────────────────────────
def _png(w: int, h: int, brut: bytes) -> bytes:
    def bloc(t: bytes, d: bytes) -> bytes:
        return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)
    return (b"\x89PNG\r\n\x1a\n" + bloc(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0))
            + bloc(b"IDAT", zlib.compress(brut, 9)) + bloc(b"IEND", b""))


def dessiner(taille: int, palette: str = "clair", retrait: float = 1.0, plein: bool = False) -> bytes:
    """le PNG du logo en `taille`×`taille`.

    `retrait` resserre le dessin (0,72 pour la version maskable, qu'Android rogne) ; `plein`
    aplatit sur le fond de la palette, parce qu'une icône d'application n'a jamais de transparence.

    Les proportions sont celles de la taille RENDUE, pas de la taille resserrée : une icône
    maskable de 512 reste une grande icône, même si son dessin n'occupe que 72 % du carré."""
    reg, pal = reglages(taille), PALETTES[palette]
    fond = tuple(v / 255.0 for v in pal["fond"])
    n = 4                                            # sur-échantillonnage n×n
    lignes = []
    for j in range(taille):
        ligne = bytearray([0])                       # filtre PNG « aucun »
        for i in range(taille):
            sr = sg = sb = sa = 0.0
            for sj in range(n):
                for si in range(n):
                    x = .5 + ((i + (si + .5) / n) / taille - .5) / retrait
                    y = .5 + ((j + (sj + .5) / n) / taille - .5) / retrait
                    r, g, b, al = pixel(x, y, reg, pal)
                    sr += r * al; sg += g * al; sb += b * al; sa += al
            if sa > 0:
                r, g, b, al = sr / sa, sg / sa, sb / sa, sa / (n * n)
            else:
                r, g, b, al = 0.0, 0.0, 0.0, 0.0
            if plein:                                # aplati sur le fond de la palette
                r, g, b = (c * al + f * (1 - al) for c, f in zip((r, g, b), fond)); al = 1.0
            ligne += bytes(int(max(0.0, min(1.0, c)) * 255 + .5) for c in (r, g, b, al))
        lignes.append(bytes(ligne))
    return _png(taille, taille, b"".join(lignes))


# nom, taille, palette, retrait, plein
ICONES = [
    # l'application installée : fond bleu plein, atome blanc — Android exige l'opacité
    ("atombox-192.png", 192, "icone", 1.0, True),
    ("atombox-512.png", 512, "icone", 1.0, True),
    ("atombox-maskable-512.png", 512, "icone", 0.72, True),
    ("apple-touch-icon.png", 180, "icone", 0.86, True),
    # l'onglet du navigateur : le dessin seul, transparent, pour tenir sur fond clair ET sombre.
    # Deux tailles VRAIES : laissé à lui-même, le navigateur rétrécit le 192 et l'on perd tout le
    # travail d'optique — à 16 px le @ du grand dessin n'est qu'une tache.
    ("atombox-32.png", 32, "clair", 1.0, False),
    ("atombox-16.png", 16, "clair", 1.0, False),
    # la marque de l'en-tête du webmail, rendue au double pour les écrans à forte densité
    ("atombox-marque-96.png", 96, "clair", 1.0, False),
]

if __name__ == "__main__":
    os.makedirs(SORTIE, exist_ok=True)
    for nom, taille, palette, retrait, plein in ICONES:
        with open(os.path.join(SORTIE, nom), "wb") as f:
            f.write(dessiner(taille, palette, retrait, plein))
        print("  icones/%s (%d px, %s%s%s)" % (nom, taille, palette,
              ", resserré %d %%" % round(retrait * 100) if retrait != 1.0 else "",
              ", opaque" if plein else ", transparent"))
