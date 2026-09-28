"""LE PROTOCOLE IMAP4rev1, côté serveur (D180) — analyse des commandes, écriture des réponses.

Ce fichier ne connaît ni la base, ni les sockets : il transforme des octets en commandes et des
valeurs en réponses. C'est ce qui le rend testable sans rien brancher, et c'est ce qui permet de le
mettre en défaut sur les cas tordus — littéraux, chaînes vides, listes imbriquées — sans monter un
serveur.

Ce qu'un client envoie :

    a001 LOGIN "jean" "mot de passe"
    a002 UID FETCH 1:* (FLAGS BODY.PEEK[])
    a003 APPEND INBOX {310}          ← un littéral : le serveur répond « + » et lit 310 octets

Les trois formes d'argument sont l'ATOME (nu), la CHAÎNE (entre guillemets, échappée) et le
LITTÉRAL (compté). Confondre les deux dernières est l'erreur classique : une chaîne peut contenir
des guillemets échappés, un littéral peut contenir n'importe quoi — y compris des CRLF.
"""
from __future__ import annotations

from ..journal import journal

log = journal("imap")


class BesoinDeLitteral(Exception):
    """l'analyse s'arrête : il faut lire `n` octets de plus avant de continuer"""
    def __init__(self, n: int): self.n = n


def decouper(ligne: str) -> list:
    """découpe une ligne de commande en éléments : str pour un atome ou une chaîne, list pour une
    parenthèse. Lève `BesoinDeLitteral` si la ligne se termine par `{n}` — le serveur doit alors
    demander la suite."""
    elements, i, n = [], 0, len(ligne)
    pile = [elements]
    while i < n:
        c = ligne[i]
        if c == " ":
            i += 1
        elif c == "(":
            neuf = []; pile[-1].append(neuf); pile.append(neuf); i += 1
        elif c == ")":
            if len(pile) > 1: pile.pop()
            i += 1
        elif c == '"':
            j, morceaux = i + 1, []
            while j < n and ligne[j] != '"':
                if ligne[j] == "\\" and j + 1 < n: j += 1        # \" et \\ — le reste passe tel quel
                morceaux.append(ligne[j]); j += 1
            pile[-1].append("".join(morceaux)); i = j + 1
        elif c == "{":
            j = ligne.find("}", i)
            if j == -1:
                log.info("littéral mal formé, commande rejetée : %.80s", ligne)
                raise ValueError("littéral mal formé")
            taille = ligne[i + 1:j].rstrip("+")                   # {12+} = littéral non bloquant
            raise BesoinDeLitteral(int(taille))
        else:
            # Un atome court jusqu'au prochain séparateur — SAUF à l'intérieur de crochets. Les
            # parenthèses de `BODY.PEEK[HEADER.FIELDS (FROM TO)]` ne sont PAS une liste : c'est un
            # seul élément, et Thunderbird envoie précisément cette forme. Les traiter comme une
            # liste coupe la commande en morceaux et l'on répond BAD à une requête parfaitement
            # légale.
            j, crochets = i, 0
            while j < n:
                c2 = ligne[j]
                if c2 == "[": crochets += 1
                elif c2 == "]": crochets -= 1
                elif crochets == 0 and c2 in ' ()"': break
                j += 1
            pile[-1].append(ligne[i:j]); i = j
    return elements


def citer(v) -> str:
    """rend une valeur comme un client l'attend : NIL, une chaîne échappée, ou un littéral.

    Un littéral dès qu'il y a un CRLF ou un octet non ASCII : une chaîne IMAP ne peut pas les
    porter, et les glisser dans des guillemets produit une réponse que le client rejette — ou pire,
    qu'il interprète de travers."""
    if v is None: return "NIL"
    if isinstance(v, int): return str(v)
    if isinstance(v, (list, tuple)): return "(" + " ".join(citer(x) for x in v) + ")"
    s = str(v)
    if "\r" in s or "\n" in s or any(ord(c) > 127 for c in s):
        b = s.encode("utf-8", "replace")
        return "{%d}\r\n%s" % (len(b), b.decode("latin-1"))
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sequence(spec: str, uids: list[int], par_uid: bool) -> list[int]:
    """résout `1:5,8,12:*` en UID réels.

    Deux pièges d'IMAP, et les deux mordent en vrai :
    - `*` est le PLUS GRAND UID existant, pas « l'infini » ni le nombre de messages ;
    - une plage est un intervalle, pas une énumération : `12:*` sur une boîte vide ne vaut rien, et
      `5:1` vaut `1:5` — les bornes peuvent être données à l'envers."""
    if not uids: return []
    plus_grand = max(uids)
    garde = set(uids)
    sortie, vus = [], set()
    for morceau in spec.split(","):
        a, _, b = morceau.partition(":")
        def borne(x, defaut):
            x = x.strip()
            if x == "*": return plus_grand
            try: return int(x)
            except ValueError: return defaut
        deb = borne(a, 1)
        fin = borne(b, deb) if b else deb
        if deb > fin: deb, fin = fin, deb
        if par_uid:
            for u in uids:
                if deb <= u <= fin and u not in vus: vus.add(u); sortie.append(u)
        else:
            for rang in range(deb, fin + 1):                      # numéro de séquence : 1 = le premier
                if 1 <= rang <= len(uids):
                    u = uids[rang - 1]
                    if u not in vus: vus.add(u); sortie.append(u)
    return sortie
