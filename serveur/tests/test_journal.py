"""Le journal (D152) : des fichiers par domaine et par sévérité, des niveaux réglables, et chaque module y écrit."""
import glob, os, re, logging, pytest
from atombox import journal as J

@pytest.fixture
def logs(tmp_path, monkeypatch):
    d = str(tmp_path / "logs")
    J.configure(log_directory=d, level="info", levels="imap=debug,auth=warning", console=False, force=True)
    yield d
    J.configure(force=True)

def read(d, nom):
    p = os.path.join(d, nom); return open(p, encoding="utf-8").read() if os.path.exists(p) else ""

def test_fichiers_par_domaine_et_par_severite(logs):
    J.journal("imap").debug("EXAMINE INBOX"); J.journal("imap").info("connecté")
    J.journal("auth").info("session ouverte"); J.journal("auth").warning("connexion refusée pour 'x'")
    J.journal("ingestion").error("NON INGÉRÉ")
    for h in logging.getLogger("atombox").handlers + logging.getLogger("atombox.imap").handlers: h.flush()
    assert "EXAMINE INBOX" in read(logs, "imap.log"), "imap est réglé en debug : le protocole s'y lit"
    assert "EXAMINE INBOX" not in read(logs, "atombox.log"), "le fichier global reste au niveau par défaut (info)"
    assert "session ouverte" not in read(logs, "auth.log") and "connexion refusée" in read(logs, "auth.log"), "auth est réglé en warning"
    assert "connexion refusée" in read(logs, "erreurs.log") and "NON INGÉRÉ" in read(logs, "erreurs.log"), "erreurs.log : WARNING et plus, tous domaines"
    assert "connecté" not in read(logs, "erreurs.log")
    assert re.search(r"^\d{4}-\d\d-\d\d \d\d:\d\d:\d\d(,\d+)? ERROR   ingestion NON INGÉRÉ", read(logs, "ingestion.log"), re.M)

def test_domaine_inconnu_refuse():
    with pytest.raises(ValueError): J.journal("nimporte")

def test_chaque_module_ecrit_dans_le_journal_et_jamais_print():
    ici = os.path.dirname(os.path.abspath(__file__)); paquet = os.path.join(ici, "..", "atombox")
    sans_journal, prints = [], []
    for f in glob.glob(os.path.join(paquet, "**", "*.py"), recursive=True):
        rel = os.path.relpath(f, paquet); s = open(f, encoding="utf-8").read()
        if re.search(r"^\s*print\(", s, re.M) and rel not in ("amorcer.py",): prints.append(rel)   # un script CLI parle sur sa sortie standard
        if rel in ("journal.py", "__init__.py", "uuid7.py") or "/migrations/" in rel or rel.startswith("schema/modeles") or rel.startswith("api/contrat") or rel.startswith("api/dependances") or rel.startswith("api/routage") or rel.startswith("ingestion/analyse") or rel.startswith("ingestion/identite") or rel.startswith("modules/__init__") or rel.endswith("__init__.py"):
            continue
        if "journal(" not in s: sans_journal.append(rel)
    assert not prints, "print() dans : " + ", ".join(prints)
    assert not sans_journal, "modules sans journal : " + ", ".join(sans_journal)
