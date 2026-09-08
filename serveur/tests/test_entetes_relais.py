"""D162 — AtomBox signe son relais dans les en-têtes, et n'y met JAMAIS l'IP de l'utilisateur.

Ce test est un garde-fou : la ligne de Received est utile, l'IP du client ne doit pas partir. Un
en-tête sortant est irrévocable — il est chez tous les destinataires avant qu'on ait vu l'erreur."""
import email, email.message, email.policy, os, re, uuid
from datetime import datetime, timezone
import pytest
from atombox.services.messages import entetes_de_relais, hote_atombox

QUAND = datetime(2026, 9, 7, 12, 30, tzinfo=timezone.utc)

def fabriquer(ip=None, tracer=None, monkeypatch=None):
    if monkeypatch is not None:
        monkeypatch.delenv("ATOMBOX_TRACER_IP_CLIENT", raising=False)
        if tracer is not None: monkeypatch.setenv("ATOMBOX_TRACER_IP_CLIENT", tracer)
        monkeypatch.setenv("ATOMBOX_HOTE", "atombox.exemple.fr")
    m = email.message.EmailMessage(policy=email.policy.SMTP)
    m["From"] = "contact@exemple.fr"; m["To"] = "jean@x.fr"; m["Subject"] = "Test"
    cid = uuid.UUID("01a07b48-c8ed-72fe-8235-f35f1511b9fe")
    entetes_de_relais(m, cid, "contact@exemple.fr", QUAND, ip_client=ip)
    m.set_content("corps")
    return m, m.as_bytes().decode("utf-8", "replace")

def test_le_received_dit_le_relais(monkeypatch):
    m, brut = fabriquer(monkeypatch=monkeypatch)
    r = m["Received"]
    assert r.startswith("from webmail (atombox) by atombox.exemple.fr with HTTPS")
    assert "id 01a07b48-c8ed-72fe-8235-f35f1511b9fe" in r, "l'identifiant de corrélation (D119, D152)"
    assert "authenticated sender: contact@exemple.fr" in r, "rien de plus que le From"
    assert "7 Sep 2026" in r and re.search(r"\+0000|GMT", r), "une date conforme RFC 5322"
    assert m["X-Mailer"] == "AtomBox" and "AtomBox/" not in brut, "sans numéro de version (surface d'attaque)"
    assert brut.index("Received:") < brut.index("From:"), "le Received est en tête, comme tout relais l'ajoute"

def test_l_ip_du_client_ne_sort_jamais_par_defaut(monkeypatch):
    m, brut = fabriquer(ip="192.0.2.42", monkeypatch=monkeypatch)
    assert "192.0.2.42" not in brut, "D162 : l'IP de l'utilisateur ne part pas — elle vit au journal"
    assert "client" not in m["Received"]

def test_l_ip_ne_sort_que_sur_reglage_explicite(monkeypatch):
    m, brut = fabriquer(ip="192.0.2.42", tracer="1", monkeypatch=monkeypatch)
    assert "(atombox (client 192.0.2.42))" in m["Received"] or "client 192.0.2.42" in m["Received"]
    m2, brut2 = fabriquer(ip="192.0.2.42", tracer="0", monkeypatch=monkeypatch)
    assert "192.0.2.42" not in brut2, "toute autre valeur que « 1 » ne trace pas"

def test_le_message_reste_analysable(monkeypatch):
    """le Received ajouté ne casse ni le parsing ni l'identité (D064)"""
    from atombox.ingestion.analyse import analyser
    from atombox.ingestion.identite import empreinte_identite
    m, brut = fabriquer(monkeypatch=monkeypatch)
    a = analyser(brut.encode())
    assert a.from_adresse == "contact@exemple.fr" and a.sujet == "Test" and a.corps_texte.strip() == "corps"
    m2, brut2 = fabriquer(ip="203.0.113.9", tracer="1", monkeypatch=monkeypatch)
    assert empreinte_identite(analyser(brut.encode())) == empreinte_identite(analyser(brut2.encode())), \
        "le Received est du transport : il ne change pas l'identité du message (D064)"

def test_l_hote_est_configurable(monkeypatch):
    monkeypatch.setenv("ATOMBOX_HOTE", "mx1.client.fr")
    assert hote_atombox() == "mx1.client.fr"
    monkeypatch.delenv("ATOMBOX_HOTE")
    assert hote_atombox(), "à défaut, le nom de la machine — jamais vide"
