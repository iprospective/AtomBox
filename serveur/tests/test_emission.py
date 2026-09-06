"""F109 — la remise au relais SMTP, contre un relais factice en mémoire (le protocole, pas le réseau)."""
import socket, threading
from atombox.emission.smtp import remettre

class RelaisFactice(threading.Thread):
    """un serveur SMTP minimal : EHLO, MAIL, RCPT, DATA, QUIT ; refuse toute adresse en @refuse.example"""
    def __init__(self):
        super().__init__(daemon=True); self.sock = socket.socket(); self.sock.bind(("127.0.0.1", 0)); self.sock.listen(1)
        self.port = self.sock.getsockname()[1]; self.recu = None; self.rcpt = []
    def run(self):
        c, _ = self.sock.accept(); f = c.makefile("rwb", buffering=0)
        def rep(x): f.write((x + "\r\n").encode())
        rep("220 factice"); data = False; corps = []
        for ligne in f:
            l = ligne.decode(errors="replace").rstrip("\r\n")
            if data:
                if l == ".": self.recu = "\n".join(corps); data = False; rep("250 OK reçu")
                else: corps.append(l)
                continue
            cmd = l.split(" ")[0].upper()
            if cmd == "EHLO": rep("250-factice"); rep("250 OK")
            elif cmd == "MAIL": rep("250 OK")
            elif cmd == "RCPT":
                self.rcpt.append(l)
                rep("550 5.1.1 inconnu" if "@refuse.example" in l else "250 OK")
            elif cmd == "DATA": data = True; rep("354 allez-y")
            elif cmd == "QUIT": rep("221 au revoir"); break
            else: rep("250 OK")
        c.close()

def test_remise_et_refus_par_destinataire():
    r = RelaisFactice(); r.start()
    cfg = {"hote": "127.0.0.1", "port": r.port, "utilisateur": None, "mot_de_passe": None, "tls": "aucun"}
    res = remettre(b"From: a@b.fr\r\nTo: c@d.fr\r\nSubject: test\r\n\r\ncorps\r\n", "a@b.fr", ["c@d.fr", "x@refuse.example"], cfg)
    r.join(timeout=5)
    assert "corps" in r.recu and len(r.rcpt) == 2
    assert list(res["refuses"]) == ["x@refuse.example"], "un refus par destinataire, pas pour l'envoi entier (D099)"

def test_sans_relais_configure():
    import pytest
    with pytest.raises(RuntimeError): remettre(b"", "a@b.fr", ["c@d.fr"], {"hote": None, "port": 25, "utilisateur": None, "mot_de_passe": None, "tls": "aucun"})

def test_le_module_est_charge_et_abonne():
    from atombox.modules import chargement
    from atombox.modules.evenements import abonnes
    charges = chargement.charger(tiers=False)
    assert "emission" in [m.nom for m in charges] and abonnes.pour("message.a_envoyer")[0][0] == "emission"
