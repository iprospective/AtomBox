"""RM3520 : les messages de la démo, du générateur (tools/fixtures-eml.js) à la boîte — et retirés sans reste.

Ce qui casserait en silence : un envoi de proposition que la règle d'en-tête ne range pas (Message-ID mal formé, hôte
oublié) ; une réponse du client qui perd le fil du document ; un message de démo qui reste après --retirer."""
import json
import os
import re
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone

import pytest
from sqlalchemy import func, select

ICI = os.path.dirname(os.path.abspath(__file__))
OUTILS = os.path.join(ICI, "..", "tools")
HOTE = "abcdef0123456789"


@pytest.fixture
def base(tmp_path, monkeypatch):
    url = os.environ.get("DATABASE_URL")
    if not url: pytest.skip("DATABASE_URL absent")
    if not shutil.which("node"): pytest.skip("node absent")
    psycopg = pytest.importorskip("psycopg")
    nom = "atombox_demo_" + uuid.uuid4().hex[:8]
    admin = psycopg.connect(url, autocommit=True); admin.execute('CREATE DATABASE "%s"' % nom)
    u = re.sub(r"/[^/?]*(\?|$)", "/" + nom + r"\1", url, count=1)
    with psycopg.connect(u) as c:
        c.execute(open(os.path.join(ICI, "..", "atombox", "schema", "schema.sql"), encoding="utf-8").read()); c.commit()
    monkeypatch.setenv("DATABASE_URL", u); monkeypatch.setenv("ATOMBOX_STORE", str(tmp_path / "magasin"))
    import atombox.db as db; db._sync.clear()
    yield u
    db.engine(u).dispose(); db._sync.clear()
    admin.execute("select pg_terminate_backend(pid) from pg_stat_activity where datname=%s and pid<>pg_backend_pid()", (nom,))
    admin.execute('DROP DATABASE "%s"' % nom); admin.close()


def test_les_messages_de_demo_se_rangent_par_les_tags_dolibarr_et_se_retirent(base, tmp_path):
    from atombox.db import session
    from atombox.ingestion.ingestion import address_of
    from atombox.schema.models import Boite, Comm, CommTag, Dossier, Tag, Axe
    from atombox.schema.seeds import seed_builtins
    from atombox.services.mailbox import ensure_mailboxes
    from atombox.uuid7 import uuid7
    from atombox import applications
    s = session()
    a = address_of(s, "demo@exemple.fr")
    b = Boite(boite_id=uuid7(), adresse_id=a.adresse_id, domaine_id=a.domaine_id, type="personnelle"); s.add(b)
    s.add(Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="INBOX", alias_imap="INBOX", protege=True))
    s.add(Dossier(dossier_id=uuid7(), boite_id=b.boite_id, nom="Sent", alias_imap="Sent", protege=True))
    s.flush(); seed_builtins(s); ensure_mailboxes(s, b.boite_id); s.commit()
    app, _jeton = applications.create(s, "doli", "dolibarr", domaines=["exemple.fr"], axes=["propal", "facture", "tiers"],
                                      parametres={"hotes": [HOTE]})
    s.commit()
    # ce que la synchronisation du module aurait poussé : le tiers (avec ses adresses) et la proposition 7
    ax = {x.nom: x for x in s.scalars(select(Axe).where(Axe.application_id == app.application_id))}
    s.add(Tag(tag_id=uuid7(), axe_id=ax["tiers"].axe_id, valeur="3", libelle="Nord SARL", actif=True,
              ref_externe={"adresses": ["julie.martin@nord-sarl.fr", "contact@nord-sarl.fr"]}))
    s.add(Tag(tag_id=uuid7(), axe_id=ax["propal"].axe_id, valeur="7", libelle="PR2611-0007 — Nord SARL", actif=True))
    s.commit()

    docs = {"societe": "iProspective", "tiers": [{"id": 3, "nom": "Nord SARL", "email": "contact@nord-sarl.fr", "demo": False,
            "contacts": [{"nom": "Julie Martin", "email": "julie.martin@nord-sarl.fr"}],
            "propositions": [{"id": 7, "ref": "PR2611-0007", "ht": 100.0, "ttc": 120.0, "etat": "signee", "date": 1793000000}],
            "factures": []}]}
    (tmp_path / "docs.json").write_text(json.dumps(docs), encoding="utf-8")
    out = tmp_path / "eml"
    r = subprocess.run(["node", os.path.join(ICI, "..", "..", "tools", "fixtures-eml.js"), "--documents", str(tmp_path / "docs.json"),
                        "--mailbox", "demo@exemple.fr", "--host", HOTE, "--out", str(out)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr

    sys.path.insert(0, OUTILS)
    import importlib.util
    spec = importlib.util.spec_from_file_location("ingest_fixtures", os.path.join(OUTILS, "ingest-fixtures.py"))
    ing = importlib.util.module_from_spec(spec); spec.loader.exec_module(ing)
    assert ing.main(["--dir", str(out), "--mailbox", "demo@exemple.fr"]) == 0
    s = session()
    n = s.scalar(select(func.count()).select_from(Comm))
    attendus = len(json.loads((out / "manifeste.json").read_text())["messages"])
    assert n == attendus and n > 2, (n, attendus)
    propal = s.scalar(select(func.count()).select_from(CommTag).join(Tag, Tag.tag_id == CommTag.tag_id).where(Tag.valeur == "7"))
    assert propal == 2, "l'envoi de la proposition ET la réponse du client (In-Reply-To) portent le tag du document : %s" % propal
    tiers = s.scalar(select(func.count()).select_from(CommTag).join(Tag, Tag.tag_id == CommTag.tag_id).where(Tag.valeur == "3"))
    assert tiers >= 2, "les messages échangés avec le tiers portent son tag (règle d'adresse) : %s" % tiers

    assert ing.main(["--dir", str(out), "--mailbox", "demo@exemple.fr"]) == 0
    assert session().scalar(select(func.count()).select_from(Comm)) == n, "rejouer ne double rien"

    assert ing.main(["--remove", "--mailbox", "demo@exemple.fr"]) == 0
    assert session().scalar(select(func.count()).select_from(Comm)) == 0, "--retirer efface tout le jeu, et ce qui en dépend"
