"""RM3645 (D205) : la collecte DÉPLACE le message à la source dans « AtomBox/Relevé », une fois stocké et vérifié.

Ce qui casserait en silence :
  - un message déplacé alors que le magasin ne le reconstitue pas à l'octet : la seule copie fidèle quitterait la boîte
    de réception, et rien ne le dirait ;
  - « AtomBox/Relevé » relevé à son tour : tout reviendrait en boucle (D205 § 3) ;
  - un message déplacé dont l'état continue de se synchroniser avec la source (D205 § 2) : son UID n'y vaut plus rien ;
  - l'option qui touche une boîte où elle n'est pas activée, ou des brouillons et des envoyés ;
  - un échec qui perd le message au lieu de le laisser à la source et de réessayer.
Un faux fournisseur (doublures.FauxImap) et une vraie base."""
from __future__ import annotations
import os, re, uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from doublures import FauxImap

RELEVE = "AtomBox/Relev&AOk-"        # « AtomBox/Relevé » en modified UTF-7, tel qu'il passe sur le fil


def _mail(n: int, sujet: str = "Message") -> bytes:
    return ("From: client%d@exemple.org\r\nTo: boite@exemple.fr\r\nSubject: %s %d\r\n"
            "Message-ID: <rm3645-%d@exemple.org>\r\nDate: Thu, 05 Nov 2026 10:0%d:00 +0100\r\n"
            "MIME-Version: 1.0\r\nContent-Type: text/plain; charset=utf-8\r\n\r\nCorps du message %d.\r\n"
            % (n, sujet, n, n, n % 10, n)).encode()


@pytest.fixture
def monde(tmp_path, monkeypatch):
    if not os.environ.get("DATABASE_URL"): pytest.skip("DATABASE_URL absent")
    import psycopg
    nom = "atombox_collecte_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(os.environ["DATABASE_URL"], autocommit=True)
    admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", os.environ["DATABASE_URL"], count=1)
    with psycopg.connect(u) as c:
        c.execute(open(os.path.join(os.path.dirname(__file__), "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    monkeypatch.setenv("DATABASE_URL", u); monkeypatch.setenv("ATOMBOX_STORE", str(tmp_path / "magasin"))
    import atombox.db as db; db._sync.clear()
    from atombox.db import session
    from atombox.ingestion.ingestion import address_of
    from atombox.schema.models import Boite
    from atombox.schema.seeds import seed_builtins
    from atombox.store import Store
    from atombox.uuid7 import uuid7
    s = session()
    a = address_of(s, "boite@exemple.fr")
    b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="personnelle"); s.add(b)
    seed_builtins(s); s.commit()
    f = FauxImap(dossiers=("INBOX", "Sent", "Drafts", "Junk")); f.start()
    yield {"s": s, "boite": b, "imap": f, "store": Store(str(tmp_path / "magasin"))}
    f.arreter(); s.close()
    db.engine(u).dispose(); db._sync.clear()
    admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
    admin.execute('DROP DATABASE "%s"' % nom); admin.close()


def _releve(m):
    """un passage complet de la relève, comme le démon le fait"""
    from atombox.ingestion.daemon import poll_mailbox
    from atombox.ingestion.imap import Poller
    p = Poller("127.0.0.1", m["imap"].port, tls=False).connect("boite@exemple.fr", "x")
    try:
        return poll_mailbox(m["s"], m["store"], p, m["boite"].boite_id, "boite@exemple.fr")
    finally:
        p.close()


def _uids(m, dossier):
    return [x["uid"] for x in m["imap"].boites.get(dossier, {"messages": []})["messages"]]


def _ratts(m):
    from atombox.schema.models import Rattachement, CommEmail
    s = m["s"]; s.expire_all()
    return {e.message_id: r for r, e in s.execute(select(Rattachement, CommEmail).join(CommEmail, CommEmail.comm_id == Rattachement.comm_id))}


def test_avec_l_option_le_message_stocke_quitte_la_boite_de_reception(monde, monkeypatch):
    m = monde
    monkeypatch.setenv("ATOMBOX_COLLECT_MOVE", "Boite@Exemple.fr, autre@exemple.fr")
    for n in (1, 2): m["imap"].put(_mail(n), "INBOX")
    m["imap"].put(_mail(3), "Junk")
    m["imap"].put(_mail(4, "Envoyé"), "Sent")
    m["imap"].put(_mail(5, "Brouillon"), "Drafts")
    assert _releve(m) == 5
    assert _uids(m, "INBOX") == [] and _uids(m, "Junk") == [], "la boîte de réception (et le courrier reçu) se vide"
    assert len(_uids(m, RELEVE)) == 3, "…dans « AtomBox/Relevé », jamais effacé"
    assert _uids(m, "Sent") == [1] and _uids(m, "Drafts") == [1], "envoyés et brouillons restent où ils sont"
    deplaces = [x["octets"] for x in m["imap"].boites[RELEVE]["messages"]]
    assert sorted(deplaces) == sorted([_mail(1), _mail(2), _mail(3)]), "les octets déplacés sont les originaux"
    r = _ratts(m)
    for n in (1, 2, 3):
        rt = r["<rm3645-%d@exemple.org>" % n]
        assert rt.uid_imap is None, "AtomBox devient la vérité : plus d'UID source, donc plus de synchronisation (D205 § 2)"
        assert m["store"].read_message(str(rt.comm_id)) == _mail(n), "le magasin reconstitue l'original à l'octet"
    assert r["<rm3645-4@exemple.org>"].uid_imap is not None and r["<rm3645-5@exemple.org>"].uid_imap is not None
    assert 'CREATE "%s"' % RELEVE in " | ".join(m["imap"].journal), "le dossier est créé s'il manque"


def test_atombox_releve_n_est_jamais_releve(monde, monkeypatch):
    m = monde
    monkeypatch.setenv("ATOMBOX_COLLECT_MOVE", "boite@exemple.fr")
    m["imap"].put(_mail(1), "INBOX")
    _releve(m)
    m["imap"].put(_mail(9, "Arrivé là par un autre chemin"), RELEVE)
    assert _releve(m) == 0, "rien n'est réingéré"
    from atombox.schema.models import Dossier
    alias = [d.alias_imap for d in m["s"].scalars(select(Dossier))]
    assert not any(a.startswith("AtomBox") for a in alias if a), alias
    assert "<rm3645-9@exemple.org>" not in _ratts(m)
    assert len(_uids(m, RELEVE)) == 2, "on ne déplace pas ce qui y est déjà"


def test_sans_l_option_rien_ne_bouge(monde, monkeypatch):
    m = monde
    monkeypatch.delenv("ATOMBOX_COLLECT_MOVE", raising=False)
    m["imap"].put(_mail(1), "INBOX")
    _releve(m)
    assert _uids(m, "INBOX") == [1] and RELEVE not in m["imap"].boites
    assert _ratts(m)["<rm3645-1@exemple.org>"].uid_imap == 1, "le régime de D193 : l'état continue de se synchroniser"
    monkeypatch.setenv("ATOMBOX_COLLECT_MOVE", "quelquun@ailleurs.fr")
    _releve(m)
    assert _uids(m, "INBOX") == [1], "une autre boîte désignée ne touche pas celle-ci"


def test_un_message_deja_releve_avant_l_option_est_deplace_ensuite(monde, monkeypatch):
    m = monde
    monkeypatch.delenv("ATOMBOX_COLLECT_MOVE", raising=False)
    m["imap"].put(_mail(1), "INBOX")
    _releve(m)
    monkeypatch.setenv("ATOMBOX_COLLECT_MOVE", "boite@exemple.fr")
    assert _releve(m) == 0
    assert _uids(m, "INBOX") == [] and len(_uids(m, RELEVE)) == 1, "l'option vide aussi ce qui était déjà relevé"
    assert _ratts(m)["<rm3645-1@exemple.org>"].uid_imap is None


def test_un_message_que_le_magasin_ne_reconstitue_pas_reste_a_la_source(monde, monkeypatch):
    m = monde
    monkeypatch.setenv("ATOMBOX_COLLECT_MOVE", "boite@exemple.fr")
    from atombox.store import Store
    vrai = Store.read_message
    monkeypatch.setattr(Store, "read_message", lambda self, cid: vrai(self, cid) + b"!")
    m["imap"].put(_mail(1), "INBOX")
    _releve(m)
    assert _uids(m, "INBOX") == [1] and not _uids(m, RELEVE), "pas exact : laissé à la source"
    assert _ratts(m)["<rm3645-1@exemple.org>"].uid_imap == 1, "…et toujours synchronisé"
    monkeypatch.setattr(Store, "read_message", vrai)
    _releve(m)
    assert _uids(m, "INBOX") == [] and len(_uids(m, RELEVE)) == 1, "rejoué au passage suivant"


def test_un_move_refuse_laisse_le_message_et_n_arrete_pas_la_releve(monde, monkeypatch):
    m = monde
    monkeypatch.setenv("ATOMBOX_COLLECT_MOVE", "boite@exemple.fr")
    from atombox.ingestion import imap
    vrai = imap.Poller.move
    def refuse(self, uid, dossier):
        raise RuntimeError("MOVE uid %d → %s : NO" % (uid, dossier))
    monkeypatch.setattr(imap.Poller, "move", refuse)
    m["imap"].put(_mail(1), "INBOX"); m["imap"].put(_mail(2), "Junk")
    assert _releve(m) == 2, "la relève continue (D152)"
    assert _uids(m, "INBOX") == [1] and _uids(m, "Junk") == [1]
    assert _ratts(m)["<rm3645-1@exemple.org>"].uid_imap == 1
    monkeypatch.setattr(imap.Poller, "move", vrai)
    _releve(m)
    assert _uids(m, "INBOX") == [] and _uids(m, "Junk") == [] and len(_uids(m, RELEVE)) == 2, "rejoué"
