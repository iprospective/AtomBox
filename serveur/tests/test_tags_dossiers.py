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
    assert {v["id"] for v in ref["valeurs"].get("service", [])} >= {"compta"}, "et ses valeurs avec"
    assert all(isinstance(a.get("label"), str) for a in ref["axes"]), "chaque axe a un libellé affichable"
