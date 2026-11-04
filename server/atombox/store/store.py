"""LE MAGASIN D'OCTETS (F002 — D005, D007, D009b, D069, D145, D145b).

Un fichier par contenu, nommé par son identifiant, sous ab/cd/<identifiant> : l'UUID de la
comm pour un message brut (préfixe temporel), l'empreinte du contenu pour un blob dédupliqué
(préfixe aléatoire). Le chemin se CALCULE, il ne se stocke pas. Un fichier n'est jamais
réécrit : le même identifiant, c'est le même contenu (ou le même message) — écrire deux fois
est un succès silencieux. Compression zstd conditionnelle (D069) : on ne compresse que si ça
gagne ; la trame zstd se reconnaît à son en-tête, donc la lecture n'a rien à savoir.

⚠ `ab/cd` NE RÉPARTIT PAS les messages (D145b, mesuré — chapitre 20 du CDC). Un UUID v7
commence par son horodatage : les quatre premiers caractères ne changent que tous les
49,7 jours, donc TOUS les messages d'une même période vivent dans le MÊME répertoire (20 000
messages mesurés : un seul répertoire ; les blobs, adressés par empreinte : 17 234). Ce n'est
pas un défaut de performance — l'accès direct reste plat (2,2 µs à 500 000 entrées) — mais
deux règles en découlent, et elles engagent tout code qui touche au magasin :

  1. ne JAMAIS supposer l'uniformité (dimensionnement, partitionnement, parallélisme) ;
  2. tout balayage se fait répertoire par répertoire — c'est-à-dire PÉRIODE par période, ce qui
     rend l'archivage par date trivial : déplacer un trimestre, c'est déplacer des répertoires.
"""
import hashlib, os, tempfile
import zstandard
from ..journal import journal

log = journal("store")

ZSTD_MAGIC = b"\x28\xb5\x2f\xfd"
GAIN_THRESHOLD = 0.10          # en dessous de 10 % gagnés, on garde les octets tels quels (D069)

def fingerprint(data: bytes) -> str:
    """l'identité d'un contenu : SHA-256 en hexadécimal — c'est aussi son nom de fichier"""
    return hashlib.sha256(data).hexdigest()

class Store:
    def __init__(self, root: str, zstd_level: int = 9):
        self.root = os.path.abspath(root)
        self._c = zstandard.ZstdCompressor(level=zstd_level)
        self._d = zstandard.ZstdDecompressor()
        os.makedirs(self.root, exist_ok=True)

    def path(self, identifiant) -> str:
        i = str(identifiant).lower()
        if len(i) < 8 or not all(c in "0123456789abcdef-" for c in i):
            raise ValueError("identifiant invalide pour le magasin : %r" % identifiant)
        return os.path.join(self.root, i[:2], i[2:4], i)

    def exists(self, identifiant) -> bool:
        return os.path.exists(self.path(identifiant))

    def write(self, identifiant, data: bytes, compress: bool | None = None, replace: bool = False) -> dict:
        """Écrit si absent ; rend {compression, taille_octets, taille_stockee, nouveau}.
        compresser=None : conditionnel (D069) ; True/False : forcé.

        `remplacer` n'existe que pour un BROUILLON, qui n'est pas encore un fait : tant qu'il
        n'est pas parti, son contenu bouge. Un message reçu ou envoyé, lui, ne se réécrit jamais
        (D025), et un blob est adressé par son empreinte — le remplacer n'aurait aucun sens."""
        path = self.path(identifiant)
        if os.path.exists(path) and not replace:
            return { "compression": self._compression_of(path), "taille_octets": len(data),
                     "taille_stockee": os.path.getsize(path), "nouveau": False }
        zst = self._c.compress(data)
        garder_zstd = compress if compress is not None else (len(zst) <= len(data) * (1 - GAIN_THRESHOLD))
        contenu = zst if garder_zstd else data
        os.makedirs(os.path.dirname(path), exist_ok=True)
        # atomique : un fichier temporaire dans le même répertoire, puis un rename
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(path))
        try:
            with os.fdopen(fd, "wb") as f: f.write(contenu); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, path)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        log.debug("écrit %s : %d → %d octets (%s)", identifiant, len(data), len(contenu), "zstd" if garder_zstd else "aucune")
        return { "compression": "zstd" if garder_zstd else "aucune", "taille_octets": len(data),
                 "taille_stockee": len(contenu), "nouveau": True }

    def put(self, data: bytes) -> tuple[str, dict]:
        """un blob adressé par son contenu (D010, D011) : l'empreinte est le nom"""
        e = fingerprint(data)
        return e, self.write(e, data)

    def read(self, identifiant) -> bytes:
        with open(self.path(identifiant), "rb") as f: contenu = f.read()
        if contenu[:4] == ZSTD_MAGIC:
            return self._d.decompress(contenu, max_output_size=1 << 31)
        return contenu

    # ── un MESSAGE (RM3631, D208, D209) : son squelette, ses pièces dans les blobs ──────────────────
    def write_message(self, comm_id, raw: bytes, replace: bool = False) -> dict:
        """Écrit le message sous l'UUID de sa comm, en SQUELETTE : ses parties base64 vont, décodées,
        dans les blobs dédupliqués. Vérifié avant de rendre : relu du disque, le message doit redonner
        l'empreinte du reçu ; sinon il est gardé ENTIER dans le conteneur (`brut_garde`), et dit.

        Rend {empreinte, taille_octets, taille_stockee, compression, brut_garde, blobs: [(empreinte, info)]} ;
        `blobs` = les pièces écrites, que l'appelant enregistre (compteur de références, D087)."""
        from . import skeleton as Sq
        h = fingerprint(raw)
        sq, segs = Sq.decompose(raw)
        blobs, manif = [], {"h": h, "segments": []}
        for sg in segs:
            e, info = self.put(sg["content"])
            blobs.append((e, info))
            manif["segments"].append(dict(sg["params"], o=sg["o"], b=e))
        info = self.write(comm_id, Sq.container(sq, manif), replace=replace)
        brut_garde = False
        try:
            ok = self.read_message(comm_id) == raw
        except Exception as ex:                               # noqa: BLE001 — tout échec est un repli
            log.warning("message %s : relecture du squelette impossible (%s)", comm_id, ex); ok = False
        if not ok:
            # garde-fou (D209) : le message ENTIER, dans le conteneur ; compté, signalé, jamais perdu
            log.warning("message %s : la reconstitution ne redonne pas l'octet reçu — brut gardé", comm_id)
            info = self.write(comm_id, Sq.container(raw, {"h": h, "segments": [], "brut": True}), replace=True)
            blobs, brut_garde = [], True
        return {"empreinte": h, "taille_octets": len(raw), "taille_stockee": info["taille_stockee"],
                "compression": "squelette-brut" if brut_garde else "squelette", "brut_garde": brut_garde, "blobs": blobs,
                "nouveau": info["nouveau"]}

    def read_message(self, comm_id) -> bytes:
        """LE chemin de lecture d'un message (RM3631) : reconstitué à l'octet, empreinte vérifiée.
        Un message d'avant RM3631 (écrit tel quel) est rendu tel quel."""
        from . import skeleton as Sq
        data = self.read(comm_id)
        c = Sq.read_container(data)
        if c is None: return data
        manif, sq = c
        raw = Sq.assemble(sq, manif, self.read)
        if fingerprint(raw) != manif.get("h"):
            raise ValueError("message %s : la reconstitution ne redonne pas l'empreinte enregistrée" % comm_id)
        return raw

    def _compression_of(self, path) -> str:
        with open(path, "rb") as f: return "zstd" if f.read(4) == ZSTD_MAGIC else "aucune"
