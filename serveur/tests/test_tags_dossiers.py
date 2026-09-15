"""RM3165 — F009/F012/F013 éprouvées : poser un tag, et un dossier virtuel qui filtre dessus.

Ce que ces tests ont trouvé en naissant : aucune route ne posait de tag, la sérialisation rendait
`tags: []` en dur, et un dossier virtuel ne savait filtrer que sur `dossier`, `from` et `sujet` —
donc jamais sur un tag, qui est pourtant sa raison d'être (D143). Trois trous sur la même chaîne :
le produit indexe « sur des critères paramétrables » (D002), et aucun n'était posable.
"""
import uuid

from test_messages import monde  # noqa: F401 — la même base jetable


def _client(monde):  # noqa: F811
    from fastapi.testclient import TestClient
    from atombox.api.app import creer_app
    import atombox.db as db
    db._async.clear(); db._sync.clear()
    c = TestClient(creer_app())
    r = c.post("/api/v1/session", json={"utilisateur": "mathieu", "mot_de_passe": "secret"})
    assert r.status_code == 200, r.text
    return c, {"Authorization": "Bearer " + r.json()["jeton"]}


def test_poser_et_retirer_un_tag(monde):  # noqa: F811
    c, h = _client(monde)
    mid = str(monde["ids"][0])

    r = c.post("/api/v1/messages/%s/tags" % mid, json={"axe": "client", "val": "Tessier"}, headers=h)
    assert r.status_code == 200, r.text
    tags = r.json()["tags"]
    assert tags == [{"axe": "client", "val": "Tessier", "source": "manuel"}]

    # le tag remonte dans le DÉTAIL et dans la LISTE — il était rendu `[]` en dur des deux côtés
    assert c.get("/api/v1/messages/" + mid, headers=h).json()["tags"][0]["val"] == "Tessier"
    liste = c.get("/api/v1/messages", params={"dossier": "inbox"}, headers=h).json()["messages"]
    porteur = next(m for m in liste if m["id"] == mid)
    assert porteur["tags"] == [{"axe": "client", "val": "Tessier", "source": "manuel"}]
    assert all(m["tags"] == [] for m in liste if m["id"] != mid), "et seulement sur celui-là"

    # poser deux fois est un succès silencieux ; un second AXE ne remplace pas le premier (D020)
    assert len(c.post("/api/v1/messages/%s/tags" % mid, json={"axe": "client", "val": "Tessier"},
                      headers=h).json()["tags"]) == 1
    deux = c.post("/api/v1/messages/%s/tags" % mid, json={"axe": "type", "val": "devis"}, headers=h).json()["tags"]
    assert {t["axe"] for t in deux} == {"client", "type"}, "plusieurs axes cohabitent, sans écrasement"

    # retirer : le tag EST la paire axe=valeur
    reste = c.delete("/api/v1/messages/%s/tags/type=devis" % mid, headers=h).json()["tags"]
    assert [t["axe"] for t in reste] == ["client"]
    assert c.delete("/api/v1/messages/%s/tags/type=devis" % mid, headers=h).status_code == 404, \
        "retirer ce qui n'est plus là : 404, pas une erreur de serveur"

    # hors portée = 404, jamais 403 (D108)
    assert c.post("/api/v1/messages/%s/tags" % uuid.uuid4(), json={"axe": "a", "val": "b"},
                  headers=h).status_code == 404
    assert c.post("/api/v1/messages/%s/tags" % mid, json={"axe": "", "val": ""}, headers=h).status_code == 404


def test_un_dossier_virtuel_filtre_sur_les_tags(monde):  # noqa: F811
    c, h = _client(monde)
    a, b = str(monde["ids"][1]), str(monde["ids"][2])
    c.post("/api/v1/messages/%s/tags" % a, json={"axe": "projet", "val": "RM2881"}, headers=h)
    c.post("/api/v1/messages/%s/tags" % b, json={"axe": "projet", "val": "RM2937"}, headers=h)

    # une VALEUR précise
    d = c.post("/api/v1/dossiers-virtuels",
               json={"label": "Projet 2881", "criteres": [{"axe": "projet", "val": "RM2881"}]},
               headers=h).json()["dossier"]
    liste = c.get("/api/v1/messages", params={"dossier": d["id"], "kind": "perso"}, headers=h).json()
    assert [m["id"] for m in liste["messages"]] == [a], "le dossier virtuel ne rend QUE le message tagué"

    # une FAMILLE : l'axe sans valeur — « tout ce qui porte un projet, quel qu'il soit »
    fam = c.post("/api/v1/dossiers-virtuels",
                 json={"label": "Tous les projets", "criteres": [{"axe": "projet"}]},
                 headers=h).json()["dossier"]
    ids = {m["id"] for m in c.get("/api/v1/messages", params={"dossier": fam["id"], "kind": "perso"},
                                  headers=h).json()["messages"]}
    assert ids == {a, b}, "la famille de tags rend les deux"

    # un message qui porte DEUX tags du même axe n'apparaît qu'une fois
    c.post("/api/v1/messages/%s/tags" % a, json={"axe": "projet", "val": "RM3165"}, headers=h)
    ids2 = [m["id"] for m in c.get("/api/v1/messages", params={"dossier": fam["id"], "kind": "perso"},
                                   headers=h).json()["messages"]]
    assert ids2.count(a) == 1, "deux tags du même axe ne dupliquent pas la ligne"

    # l'arborescence sert les dossiers virtuels, et sa suppression emporte l'épingle (D144)
    arbo = c.get("/api/v1/arborescence", headers=h).json()
    assert any(v["id"] == d["id"] for v in arbo.get("virtuels", [])), "il apparaît dans l'arborescence"
    c.put("/api/v1/parametres", json={"cle": "epingles", "valeur": [d["id"]]}, headers=h)
    assert c.delete("/api/v1/dossiers-virtuels/" + d["id"], headers=h).json()["supprimes"] == 1
    apres = c.get("/api/v1/arborescence", headers=h).json()
    assert not any(v["id"] == d["id"] for v in apres.get("virtuels", []))
    assert d["id"] not in (c.get("/api/v1/parametres", headers=h).json().get("epingles") or []), \
        "supprimer un dossier virtuel retire son épingle — sinon l'épingle pointe un mort"


def test_les_axes_remontent_aux_referentiels(monde):  # noqa: F811
    """RM3176 — ils étaient rendus `[]` et `{}` en dur : le formulaire « mes dossiers + » faisait
    `axes[0].id` sur une liste vide et mourait en silence."""
    c, h = _client(monde)
    mid = str(monde["ids"][3])
    c.post("/api/v1/messages/%s/tags" % mid, json={"axe": "service", "val": "compta"}, headers=h)
    ref = c.get("/api/v1/referentiels", headers=h).json()
    assert any(a["id"] == "service" for a in ref["axes"]), "l'axe créé à la volée est servi"
    vals = ref["valeurs"].get("service", [])
    # l'identifiant d'une valeur est « axe:valeur » — c'est le SERVEUR qui fixe ce contrat (D141),
    # et le client le renvoie tel quel pour ouvrir la branche (RM3197)
    assert {v["id"] for v in vals} >= {"service:compta"}, "l'identifiant porte l'axe"
    assert {v["label"] for v in vals} >= {"compta"}, "et le libellé reste la valeur nue"
    assert all(isinstance(a.get("label"), str) for a in ref["axes"]), "chaque axe a un libellé affichable"


def test_un_dossier_virtuel_est_compte(monde):  # noqa: F811
    """Il affichait 0/0 en portant des messages : aucun `GROUP BY dossier_id` ne voit un dossier
    qui n'existe pas en base. Le compteur et la liste doivent dire la MÊME chose."""
    c, h = _client(monde)
    a = str(monde["ids"][0])
    c.post("/api/v1/messages/%s/tags" % a, json={"axe": "compté", "val": "oui"}, headers=h)
    d = c.post("/api/v1/dossiers-virtuels",
               json={"label": "Compté", "criteres": [{"axe": "compté", "val": "oui"}]},
               headers=h).json()["dossier"]

    arbo = c.get("/api/v1/arborescence", headers=h).json()
    compte = arbo["compteurs"].get(d["id"])
    assert compte, "le dossier virtuel a un compteur — il n'en avait aucun, d'où le 0/0"
    liste = c.get("/api/v1/messages", params={"dossier": d["id"], "kind": "perso"}, headers=h).json()
    assert compte["t"] == liste["total"] == 1, "le compteur dit ce que la liste montre"

    # un second message tagué : les deux suivent
    b = str(monde["ids"][1])
    c.post("/api/v1/messages/%s/tags" % b, json={"axe": "compté", "val": "oui"}, headers=h)
    arbo2 = c.get("/api/v1/arborescence", headers=h).json()
    liste2 = c.get("/api/v1/messages", params={"dossier": d["id"], "kind": "perso"}, headers=h).json()
    assert arbo2["compteurs"][d["id"]]["t"] == liste2["total"] == 2
    assert arbo2["compteurs"][d["id"]]["u"] <= 2, "et les non-lus sont un sous-ensemble"


def test_les_branches_d_axes_listent_et_comptent(monde):  # noqa: F811
    """RM3197 — elles étaient affichées, vides et à zéro : la liste ne savait pas filtrer une
    branche, et aucun GROUP BY dossier_id ne voit un axe."""
    c, h = _client(monde)
    a, b = str(monde["ids"][0]), str(monde["ids"][1])
    c.post("/api/v1/messages/%s/tags" % a, json={"axe": "branche", "val": "un"}, headers=h)
    c.post("/api/v1/messages/%s/tags" % b, json={"axe": "branche", "val": "deux"}, headers=h)
    c.post("/api/v1/messages/%s/tags" % a, json={"axe": "branche", "val": "trois"}, headers=h)

    # une VALEUR précise
    l1 = c.get("/api/v1/messages", params={"dossier": "branche:un", "kind": "virtuel"}, headers=h).json()
    assert [m["id"] for m in l1["messages"]] == [a], "la branche d'une valeur liste ses messages"

    # la TÊTE d'axe : toute la famille, et un message à deux valeurs ne compte qu'une fois
    tete = c.get("/api/v1/messages", params={"dossier": "axe:branche", "kind": "axe"}, headers=h).json()
    assert {m["id"] for m in tete["messages"]} == {a, b}, "la tête liste toute la famille"
    assert tete["total"] == 2, "et un message portant deux valeurs du même axe n'y figure qu'une fois"

    arbo = c.get("/api/v1/arborescence", headers=h).json()["compteurs"]
    assert arbo["branche:un"]["t"] == 1 and arbo["branche:deux"]["t"] == 1
    assert arbo["axe:branche"]["t"] == 2, "la tête compte comme elle liste — pas trois pour deux messages"


def test_une_branche_de_classement_montre_aussi_les_traites(monde):  # noqa: F811
    """D166 — « traité sort de la file » vaut pour une FILE de travail ; appliquée à un tag, elle
    ferait disparaître un projet entier dès qu'il est terminé. Une branche de classement s'ouvre
    sur « tous », et son compteur compte ce qu'elle liste."""
    c, h = _client(monde)
    a, b = str(monde["ids"][0]), str(monde["ids"][2])
    c.post("/api/v1/messages/%s/tags" % a, json={"axe": "file", "val": "x"}, headers=h)
    c.post("/api/v1/messages/%s/tags" % b, json={"axe": "file", "val": "x"}, headers=h)

    # on en traite un : il sort de la FILE, pas du classement
    c.patch("/api/v1/messages/%s/rattachement" % b,
            json={"statut": "traite", "motif_sortie": "traite"}, headers=h)

    tous = c.get("/api/v1/messages", params={"dossier": "file:x", "kind": "virtuel", "filtre": "tous"},
                 headers=h).json()
    assert tous["total"] == 2, "la branche montre le message traité — c'est lui qu'on vient consulter"
    arbo = c.get("/api/v1/arborescence", headers=h).json()["compteurs"]
    assert arbo["file:x"]["t"] == 2 and arbo["axe:file"]["t"] == 2, "le compteur dit ce que la liste montre"

    # et le filtre « en file » reste disponible pour restreindre
    file = c.get("/api/v1/messages", params={"dossier": "file:x", "kind": "virtuel", "filtre": "file"},
                 headers=h).json()
    assert file["total"] == 1, "« en file » écarte toujours ce qui est traité"
    sortis = c.get("/api/v1/messages", params={"dossier": "file:x", "kind": "virtuel", "filtre": "sortis"},
                   headers=h).json()
    assert sortis["total"] == 1, "et « traités / archivés » ne montre que lui"
