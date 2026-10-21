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


class LiteralNeeded(Exception):
    """l'analyse s'arrête : il faut lire `n` octets de plus avant de continuer"""
    def __init__(self, n: int): self.n = n


def parse_line(line: str) -> list:
    """découpe une ligne de commande en éléments : str pour un atome ou une chaîne, list pour une
    parenthèse. Lève `BesoinDeLitteral` si la ligne se termine par `{n}` — le serveur doit alors
    demander la suite."""
    elements, i, n = [], 0, len(line)
    stack = [elements]
    while i < n:
        c = line[i]
        if c == " ":
            i += 1
        elif c == "(":
            fresh = []; stack[-1].append(fresh); stack.append(fresh); i += 1
        elif c == ")":
            if len(stack) > 1: stack.pop()
            i += 1
        elif c == '"':
            j, chunks = i + 1, []
            while j < n and line[j] != '"':
                if line[j] == "\\" and j + 1 < n: j += 1        # \" et \\ — le reste passe tel quel
                chunks.append(line[j]); j += 1
            stack[-1].append("".join(chunks)); i = j + 1
        elif c == "{":
            j = line.find("}", i)
            if j == -1:
                log.info("littéral mal formé, commande rejetée : %.80s", line)
                raise ValueError("littéral mal formé")
            size = line[i + 1:j].rstrip("+")                   # {12+} = littéral non bloquant
            raise LiteralNeeded(int(size))
        else:
            # Un atome court jusqu'au prochain séparateur — SAUF à l'intérieur de crochets. Les
            # parenthèses de `BODY.PEEK[HEADER.FIELDS (FROM TO)]` ne sont PAS une liste : c'est un
            # seul élément, et Thunderbird envoie précisément cette forme. Les traiter comme une
            # liste coupe la commande en morceaux et l'on répond BAD à une requête parfaitement
            # légale.
            j, brackets = i, 0
            while j < n:
                c2 = line[j]
                if c2 == "[": brackets += 1
                elif c2 == "]": brackets -= 1
                elif brackets == 0 and c2 in ' ()"': break
                j += 1
            stack[-1].append(line[i:j]); i = j
    return elements


def quote(v) -> str:
    """rend une valeur comme un client l'attend : NIL, une chaîne échappée, ou un littéral.

    Un littéral dès qu'il y a un CRLF ou un octet non ASCII : une chaîne IMAP ne peut pas les
    porter, et les glisser dans des guillemets produit une réponse que le client rejette — ou pire,
    qu'il interprète de travers."""
    if v is None: return "NIL"
    if isinstance(v, int): return str(v)
    if isinstance(v, (list, tuple)): return "(" + " ".join(quote(x) for x in v) + ")"
    s = str(v)
    if "\r" in s or "\n" in s or any(ord(c) > 127 for c in s):
        b = s.encode("utf-8", "replace")
        return "{%d}\r\n%s" % (len(b), b.decode("latin-1"))
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def sequence(spec: str, uids: list[int], by_uid: bool) -> list[int]:
    """résout `1:5,8,12:*` en UID réels.

    Deux pièges d'IMAP, et les deux mordent en vrai :
    - `*` est le PLUS GRAND UID existant, pas « l'infini » ni le nombre de messages ;
    - une plage est un intervalle, pas une énumération : `12:*` sur une boîte vide ne vaut rien, et
      `5:1` vaut `1:5` — les bornes peuvent être données à l'envers."""
    if not uids: return []
    largest = max(uids)
    keep = set(uids)
    out, seen = [], set()
    for chunk in spec.split(","):
        a, _, b = chunk.partition(":")
        def bound(x, default):
            x = x.strip()
            if x == "*": return largest
            try: return int(x)
            except ValueError: return default
        start = bound(a, 1)
        fin = bound(b, start) if b else start
        if start > fin: start, fin = fin, start
        if by_uid:
            for u in uids:
                if start <= u <= fin and u not in seen: seen.add(u); out.append(u)
        else:
            for rank in range(start, fin + 1):                      # numéro de séquence : 1 = le premier
                if 1 <= rank <= len(uids):
                    u = uids[rank - 1]
                    if u not in seen: seen.add(u); out.append(u)
    return out
