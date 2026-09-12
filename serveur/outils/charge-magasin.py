#!/usr/bin/env python3
"""charge-magasin — ce que le magasin d'octets fait à volume (D145, V0).

D145 a tranché `ab/cd/<id>`, UUID v7 pour les messages, empreinte pour les blobs — et a
demandé un test de charge avant de s'y tenir. Le voici : il MESURE, il ne suppose pas.

    python3 outils/charge-magasin.py [--messages 20000] [--racine /chemin] [--json]

Quatre choses mesurées, dans cet ordre d'importance :
  1. la RÉPARTITION réelle des identifiants sur `ab/cd` — combien de répertoires, et le pire ;
  2. le DÉBIT d'écriture, réparti contre concentré dans un seul répertoire ;
  3. le coût de LIRE : ouverture d'un fichier au hasard, et parcours d'un répertoire chargé ;
  4. ce que la COMPRESSION conditionnelle (D069) gagne sur des messages à la bonne taille.

Les tailles suivent la distribution mesurée au chapitre 15 : médiane 7,5 ko, moyenne 86 ko
(log-normale calibrée dessus). Un test de charge sur des messages de taille égale ne mesure
rien : c'est la queue qui coûte.
"""
import argparse
import base64
import json as _json
import math
import os
import random
import shutil
import statistics
import sys
import tempfile
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from atombox.magasin.magasin import Magasin, empreinte   # noqa: E402
from atombox.uuid7 import uuid7                          # noqa: E402

# chapitre 15 : médiane 7 532 o, moyenne 86 ko — une log-normale calée sur ces deux nombres
MEDIANE, MOYENNE = 7532, 86000
MU = math.log(MEDIANE)
SIGMA = math.sqrt(2 * math.log(MOYENNE / MEDIANE))

LOREM = ("Bonjour, nous accusons réception de votre demande. Un retour vous sera fait sous 48 heures. "
         "Pourriez-vous nous confirmer les quantités avant expédition ? Cordialement, le service commercial. ")


def taille_tiree(rnd) -> int:
    return max(400, min(30 * 1024 * 1024, int(rnd.lognormvariate(MU, SIGMA))))


def message(rnd, taille: int) -> bytes:
    """Un message plausible : en-têtes, corps en français, et au-delà de 20 ko une pièce
    jointe en base64 — sinon on mesurerait la compression d'un texte pur, qui n'existe pas."""
    tete = ("Message-ID: <%s@exemple.fr>\r\nFrom: Camille Martin <camille@exemple.fr>\r\n"
            "To: contact@exemple.fr\r\nSubject: Commande %d\r\n"
            "Date: Thu, 11 Sep 2026 09:12:%02d +0200\r\n\r\n" % (uuid7(), rnd.randint(1000, 9999), rnd.randint(0, 59)))
    reste = max(0, taille - len(tete))
    if taille <= 20 * 1024:
        corps = (LOREM * (reste // len(LOREM) + 1))[:reste]
        return (tete + corps).encode()
    texte = (LOREM * 8)[:2000]
    # Une vraie pièce jointe (JPEG, PDF, ZIP) est DÉJÀ compressée : la simuler avec du texte
    # répété ferait mesurer un gain de compression qui n'existe pas, et dimensionner faux.
    brut = os.urandom(int((reste - len(texte)) * 3 / 4) + 3)
    b64 = base64.b64encode(brut).decode()[:reste - len(texte)]
    return (tete + texte + b64).encode()


def pct(v, n):
    return "%.1f %%" % (100.0 * v / n) if n else "—"


def mesurer(nb: int, racine: str, graine: int = 42) -> dict:
    rnd = random.Random(graine)
    mag = Magasin(racine)
    res = {"messages": nb, "mesure_le": time.strftime("%Y-%m-%dT%H:%M:%S")}

    # --- 1. répartition : ce que `ab/cd` fait d'un UUID v7 -------------------
    ids = [str(uuid7()) for _ in range(nb)]
    feuilles = {}
    for i in ids:
        feuilles[i[:2] + "/" + i[2:4]] = feuilles.get(i[:2] + "/" + i[2:4], 0) + 1
    emps = [empreinte(("%d" % k).encode()) for k in range(nb)]
    feuilles_emp = {}
    for e in emps:
        feuilles_emp[e[:2] + "/" + e[2:4]] = feuilles_emp.get(e[:2] + "/" + e[2:4], 0) + 1
    res["repartition"] = {
        "uuid7": {"repertoires": len(feuilles), "max_par_repertoire": max(feuilles.values()),
                  "median_par_repertoire": statistics.median(feuilles.values())},
        "empreinte": {"repertoires": len(feuilles_emp), "max_par_repertoire": max(feuilles_emp.values()),
                      "median_par_repertoire": statistics.median(feuilles_emp.values())},
    }

    # --- 2. écriture, et ce que la compression gagne ------------------------
    tailles = [taille_tiree(rnd) for _ in range(nb)]
    corpus = [message(rnd, t) for t in tailles]
    logique = sum(len(c) for c in corpus)
    t0 = time.monotonic()
    stocke = comprimes = 0
    for i, c in zip(ids, corpus):
        info = mag.ecrire(i, c)
        stocke += info["taille_stockee"]
        comprimes += 1 if info["compression"] == "zstd" else 0
    duree = time.monotonic() - t0
    res["ecriture"] = {"duree_s": round(duree, 2), "messages_par_s": round(nb / duree, 1),
                       "mo_par_s": round(logique / duree / 1048576, 1)}
    res["compression"] = {"logique_mo": round(logique / 1048576, 1), "stocke_mo": round(stocke / 1048576, 1),
                          "gain": pct(logique - stocke, logique), "comprimes": comprimes,
                          "part_comprimee": pct(comprimes, nb)}
    res["tailles"] = {"mediane_o": int(statistics.median(tailles)), "moyenne_o": int(statistics.fmean(tailles)),
                      "max_o": max(tailles)}

    # --- 3. lire : un fichier au hasard, puis parcourir le pire répertoire ---
    echantillon = rnd.sample(ids, min(2000, nb))
    t0 = time.monotonic()
    for i in echantillon:
        mag.lire(i)
    d = time.monotonic() - t0
    res["lecture"] = {"lectures": len(echantillon), "duree_s": round(d, 2),
                      "par_s": round(len(echantillon) / d, 1), "ms_par_lecture": round(1000 * d / len(echantillon), 3)}
    pire = max(feuilles, key=feuilles.get)
    chemin = os.path.join(racine, *pire.split("/"))
    t0 = time.monotonic()
    entrees = sum(1 for _ in os.scandir(chemin))
    res["parcours_repertoire"] = {"repertoire": pire, "entrees": entrees,
                                  "duree_ms": round(1000 * (time.monotonic() - t0), 1)}
    t0 = time.monotonic()
    for e in os.scandir(chemin):
        e.stat()
    res["parcours_repertoire"]["stat_ms"] = round(1000 * (time.monotonic() - t0), 1)

    # --- 4. jusqu'où un répertoire tient ------------------------------------
    res["annuaire"] = annuaire([10_000, 50_000, 200_000, 500_000], racine)
    return res



def annuaire(paliers, racine) -> list:
    """Ce qu'un RÉPERTOIRE coûte quand il grossit — fichiers vides : on mesure l'annuaire du
    système de fichiers, pas les octets. C'est ce chiffre qui dit si `ab/cd` tient : avec un
    UUID v7, tous les messages d'une même période partagent le même répertoire."""
    out = []
    d = os.path.join(racine, "_annuaire")
    os.makedirs(d, exist_ok=True)
    fait = 0
    for n in paliers:
        t0 = time.monotonic()
        for k in range(fait, n):
            open(os.path.join(d, "%032x" % k), "wb").close()
        creation = time.monotonic() - t0
        fait = n
        t0 = time.monotonic(); entrees = sum(1 for _ in os.scandir(d)); parcours = time.monotonic() - t0
        t0 = time.monotonic()
        for e in os.scandir(d):
            e.stat()
        avec_stat = time.monotonic() - t0
        cibles = ["%032x" % random.randrange(n) for _ in range(500)]
        t0 = time.monotonic()
        for c in cibles:
            os.stat(os.path.join(d, c))
        acces = time.monotonic() - t0
        out.append({"entrees": entrees, "creation_par_s": round((n - (paliers[paliers.index(n) - 1] if paliers.index(n) else 0)) / creation),
                    "parcours_ms": round(1000 * parcours, 1), "parcours_stat_ms": round(1000 * avec_stat, 1),
                    "acces_direct_us": round(1_000_000 * acces / len(cibles), 1)})
    shutil.rmtree(d, ignore_errors=True)
    return out


def rendre(r: dict) -> None:
    rep = r["repartition"]
    print("== charge du magasin — %d messages, %s ==" % (r["messages"], r["mesure_le"]))
    print("\n-- répartition sur `ab/cd` --")
    print("  %-12s %10s %12s %12s" % ("adressage", "répertoires", "médiane/rép", "pire/rép"))
    for k, lib in (("uuid7", "UUID v7"), ("empreinte", "empreinte")):
        v = rep[k]
        print("  %-12s %10d %12.0f %12d" % (lib, v["repertoires"], v["median_par_repertoire"], v["max_par_repertoire"]))
    print("\n-- écriture --")
    print("  %s messages en %ss — %s msg/s, %s Mo/s"
          % (r["messages"], r["ecriture"]["duree_s"], r["ecriture"]["messages_par_s"], r["ecriture"]["mo_par_s"]))
    c = r["compression"]
    print("\n-- compression conditionnelle (D069) --")
    print("  %s Mo logiques → %s Mo stockés (gain %s) ; %s des messages compressés"
          % (c["logique_mo"], c["stocke_mo"], c["gain"], c["part_comprimee"]))
    t = r["tailles"]
    print("  tailles tirées : médiane %d o, moyenne %d o, max %.1f Mo"
          % (t["mediane_o"], t["moyenne_o"], t["max_o"] / 1048576))
    l = r["lecture"]
    print("\n-- lecture --")
    print("  %d lectures au hasard : %s ms chacune (%s /s)" % (l["lectures"], l["ms_par_lecture"], l["par_s"]))
    p = r["parcours_repertoire"]
    print("  parcours du pire répertoire (%s, %d entrées) : %s ms ; avec stat() : %s ms"
          % (p["repertoire"], p["entrees"], p["duree_ms"], p["stat_ms"]))
    if r.get("annuaire"):
        print("\n-- jusqu'où un seul répertoire tient (fichiers vides) --")
        print("  %10s %14s %12s %16s %14s" % ("entrées", "création/s", "parcours", "parcours+stat", "accès direct"))
        for a in r["annuaire"]:
            print("  %10d %14d %10s ms %13s ms %11s µs"
                  % (a["entrees"], a["creation_par_s"], a["parcours_ms"], a["parcours_stat_ms"], a["acces_direct_us"]))


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--messages", type=int, default=20000)
    ap.add_argument("--racine", help="défaut : un répertoire temporaire, effacé à la fin")
    ap.add_argument("--garder", action="store_true", help="ne pas effacer la racine temporaire")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    racine = a.racine or tempfile.mkdtemp(prefix="atombox-charge-")
    try:
        r = mesurer(a.messages, racine)
        print(_json.dumps(r, ensure_ascii=False, indent=1) if a.json else "", end="")
        if not a.json:
            rendre(r)
    finally:
        if not a.racine and not a.garder:
            shutil.rmtree(racine, ignore_errors=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
