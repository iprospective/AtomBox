"""LE MAGASIN D'OCTETS (F002 — D005, D007, D009b, D069, D145).

Un fichier par contenu, nommé par son identifiant, sous ab/cd/<identifiant> : l'UUID de la
comm pour un message brut (préfixe temporel), l'empreinte du contenu pour un blob dédupliqué
(préfixe aléatoire). Le chemin se CALCULE, il ne se stocke pas. Un fichier n'est jamais
réécrit : le même identifiant, c'est le même contenu (ou le même message) — écrire deux fois
est un succès silencieux. Compression zstd conditionnelle (D069) : on ne compresse que si ça
gagne ; la trame zstd se reconnaît à son en-tête, donc la lecture n'a rien à savoir.
"""
import hashlib, os, tempfile
import zstandard
from ..journal import journal

log = journal("magasin")

MAGIE_ZSTD = b"\x28\xb5\x2f\xfd"
SEUIL_GAIN = 0.10          # en dessous de 10 % gagnés, on garde les octets tels quels (D069)

def empreinte(octets: bytes) -> str:
    """l'identité d'un contenu : SHA-256 en hexadécimal — c'est aussi son nom de fichier"""
    return hashlib.sha256(octets).hexdigest()

class Magasin:
    def __init__(self, racine: str, niveau_zstd: int = 9):
        self.racine = os.path.abspath(racine)
        self._c = zstandard.ZstdCompressor(level=niveau_zstd)
        self._d = zstandard.ZstdDecompressor()
        os.makedirs(self.racine, exist_ok=True)

    def chemin(self, identifiant) -> str:
        i = str(identifiant).lower()
        if len(i) < 8 or not all(c in "0123456789abcdef-" for c in i):
            raise ValueError("identifiant invalide pour le magasin : %r" % identifiant)
        return os.path.join(self.racine, i[:2], i[2:4], i)

    def existe(self, identifiant) -> bool:
        return os.path.exists(self.chemin(identifiant))

    def ecrire(self, identifiant, octets: bytes, compresser: bool | None = None, remplacer: bool = False) -> dict:
        """Écrit si absent ; rend {compression, taille_octets, taille_stockee, nouveau}.
        compresser=None : conditionnel (D069) ; True/False : forcé.

        `remplacer` n'existe que pour un BROUILLON, qui n'est pas encore un fait : tant qu'il
        n'est pas parti, son contenu bouge. Un message reçu ou envoyé, lui, ne se réécrit jamais
        (D025), et un blob est adressé par son empreinte — le remplacer n'aurait aucun sens."""
        chemin = self.chemin(identifiant)
        if os.path.exists(chemin) and not remplacer:
            return { "compression": self._compression_de(chemin), "taille_octets": len(octets),
                     "taille_stockee": os.path.getsize(chemin), "nouveau": False }
        zst = self._c.compress(octets)
        garder_zstd = compresser if compresser is not None else (len(zst) <= len(octets) * (1 - SEUIL_GAIN))
        contenu = zst if garder_zstd else octets
        os.makedirs(os.path.dirname(chemin), exist_ok=True)
        # atomique : un fichier temporaire dans le même répertoire, puis un rename
        fd, tmp = tempfile.mkstemp(prefix=".tmp-", dir=os.path.dirname(chemin))
        try:
            with os.fdopen(fd, "wb") as f: f.write(contenu); f.flush(); os.fsync(f.fileno())
            os.replace(tmp, chemin)
        finally:
            if os.path.exists(tmp): os.unlink(tmp)
        log.debug("écrit %s : %d → %d octets (%s)", identifiant, len(octets), len(contenu), "zstd" if garder_zstd else "aucune")
        return { "compression": "zstd" if garder_zstd else "aucune", "taille_octets": len(octets),
                 "taille_stockee": len(contenu), "nouveau": True }

    def deposer(self, octets: bytes) -> tuple[str, dict]:
        """un blob adressé par son contenu (D010, D011) : l'empreinte est le nom"""
        e = empreinte(octets)
        return e, self.ecrire(e, octets)

    def lire(self, identifiant) -> bytes:
        with open(self.chemin(identifiant), "rb") as f: contenu = f.read()
        if contenu[:4] == MAGIE_ZSTD:
            return self._d.decompress(contenu, max_output_size=1 << 31)
        return contenu

    def _compression_de(self, chemin) -> str:
        with open(chemin, "rb") as f: return "zstd" if f.read(4) == MAGIE_ZSTD else "aucune"
