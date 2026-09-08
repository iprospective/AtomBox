/* CONTRÔLEUR ADMINISTRATION + PIÈCES JOINTES — deux onglets particuliers. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, C = ABX.Corpus, F = ABX.Fmt;

  const Admin = {
    ouvrir(volet) {
      ABX.Controllers.Tabs.ouvrir({ type:"admin", volet: volet || "boites" }, false);
    },
    ouvrirPJ() { ABX.Controllers.Tabs.ouvrir({ type:"pj" }, false); },

    peindre(t) {
      const el = D.paint("detail", ABX.Views.Admin.render(t.volet));
      ABX.Controllers.App.bindRetour(el);
      D.on(el, ".chip[data-vol]", "onclick", c => { t.volet = c.dataset.vol; St.save();
                                                    Admin.peindre(t); Admin.log(t.volet); });
      D.on(el, ".chip[data-cap]", "onclick", c =>
        ABX.Providers.choisir(c.dataset.cap, c.dataset.f));
      D.on(el, "[data-adm]", "onclick", b => Admin.geste(b.dataset.adm));
      Admin.brancherEtat(t, el);
      Admin.brancherRegles(t, el);
      Admin.log(t.volet);
    },

    /* ---- État & journal (F122) : deux chargements par promesse, deux repeintures ---------- */
    brancherEtat(t, el) {
      const V = ABX.Views.Admin;
      if (t.volet !== "etat") return;
      if (!V._etat && !V._etatEnCours) { V._etatEnCours = true;
        ABX.Api.etat().then(e => { V._etat = e; V._etatEnCours = false; Admin.peindre(t); },
                            () => { V._etatEnCours = false; }); }
      if (!V._journal && !V._journalEnCours) Admin.chargerJournal(t);
      if (!V._etat) return;                       // rien à câbler tant que la page dit « Chargement… »
      D.byId("etat-recharger").onclick = () => { V._etat = null; V._journal = null; Admin.peindre(t); };
      ["j-domaine", "j-niveau", "j-filtre"].forEach(id => {
        const c = D.byId(id);
        const relire = () => {
          V._jd = D.byId("j-domaine").value; V._jn = D.byId("j-niveau").value; V._jf = D.byId("j-filtre").value;
          V._journal = null; Admin.chargerJournal(t);
        };
        if (id === "j-filtre") { c.onkeydown = e => { if (e.key === "Enter") relire(); }; }
        else c.onchange = relire;
      });
    },

    chargerJournal(t) {
      const V = ABX.Views.Admin;
      V._journalEnCours = true;
      return ABX.Api.journal(V._jd || "atombox", V._jn || "INFO", V._jf || "")
        .then(l => { V._journal = l; V._journalEnCours = false; if (St.ui.tab === t.key) Admin.peindre(t); },
              () => { V._journal = []; V._journalEnCours = false; });
    },

    /* ---- Règles (F016) : lister, créer, activer, supprimer -------------------------------- */
    brancherRegles(t, el) {
      const V = ABX.Views.Admin;
      if (t.volet !== "regles") return;
      if (!V._filtres && !V._filtresEnCours) { V._filtresEnCours = true;
        ABX.Api.filtres().then(d => { V._filtres = d; V._filtresEnCours = false; Admin.peindre(t); },
                               () => { V._filtresEnCours = false; }); }
      const recharger = () => { V._filtres = null; V._nouvelle = null; Admin.peindre(t); };
      if (!V._filtres) return;
      D.byId("r-nouvelle").onclick = () => {
        const d = V._filtres || {};
        V._nouvelle = { nom: "", mode: "et", action: (d.actions || ["classer"])[0], dossier: "",
                        criteres: [{ champ: (d.champs || ["from"])[0], operateur: "contient", valeur: "" }] };
        Admin.peindre(t);
      };
      D.on(el, "[data-rtoggle]", "onclick", b => {
        const f = (V._filtres.filtres || []).find(x => x.id === b.dataset.rtoggle);
        ABX.Api.modifierFiltre(f.id, { actif: !f.actif }).then(recharger, recharger);
      });
      D.on(el, "[data-rdel]", "onclick", b => {
        if (!confirm("Supprimer cette règle ? Aucun message n'est touché.")) return;
        ABX.Api.supprimerFiltre(b.dataset.rdel).then(recharger, recharger);
      });
      if (!V._nouvelle) return;
      const lire = () => {
        const f = V._nouvelle;
        f.nom = D.byId("r-nom").value; f.action = D.byId("r-action").value;
        f.dossier = D.byId("r-dossier").value;
        f.criteres.forEach((c, i) => {
          c.champ = D.byId("r-champ-" + i).value;
          c.operateur = D.byId("r-op-" + i).value;
          c.valeur = D.byId("r-val-" + i).value;
        });
      };
      D.byId("r-mode").onclick = () => { lire(); V._nouvelle.mode = V._nouvelle.mode === "ou" ? "et" : "ou"; Admin.peindre(t); };
      D.byId("r-plus").onclick = () => { lire(); V._nouvelle.criteres.push({ champ: (V._filtres.champs || ["from"])[0], operateur: "contient", valeur: "" }); Admin.peindre(t); };
      D.byId("r-action").onchange = () => { lire(); Admin.peindre(t); };
      D.byId("r-non").onclick = () => { V._nouvelle = null; Admin.peindre(t); };
      D.byId("r-ok").onclick = () => {
        lire();
        const f = V._nouvelle;
        const action = { type: f.action };
        if (f.action === "classer" && f.dossier) action.dossier = f.dossier;
        ABX.Api.creerFiltre({ nom: f.nom, portee: "compte",
                              predicat: { mode: f.mode, criteres: f.criteres.filter(c => c.valeur || c.operateur === "existe") },
                              action })
          .then(recharger, e => { alert("Règle refusée : " + (e && e.message || e)); });
      };
    },

    log(volet) {
      const L = {
        boites: ["Administration — domaines et boîtes",
`SELECT d.nom, d.role, count(DISTINCT b.boite_id) FILTER (WHERE b.alias_de IS NULL) AS boites,
       count(DISTINCT b.boite_id) FILTER (WHERE b.alias_de IS NOT NULL) AS alias
  FROM domaine d LEFT JOIN boite b USING (domaine_id)
 GROUP BY d.nom, d.role;`,
          "un alias est une BOÎTE, pas une redirection (D039) : d'où alias_de plutôt qu'une " +
          "table à part — et d'où le fait qu'un message adressé à un alias garde son destinataire"],
        apps: ["Administration — applications et jetons",
`SELECT a.code, a.libelle, a.derniere_vue,
       array_agg(DISTINCT ax.axe_id) AS axes,
       array_agg(DISTINCT p.boite_id) AS portee
  FROM application a
  LEFT JOIN acl_axe ax ON ax.application_id = a.application_id
  LEFT JOIN portee_application p ON p.application_id = a.application_id
 GROUP BY a.application_id;`,
          "le jeton n'apparaît PAS dans cette requête : on stocke son empreinte, jamais sa " +
          "valeur (D063) — un jeton perdu se régénère, il ne se relit pas"],
        axes: ["Administration — axes et volumétrie des tags",
`SELECT ax.axe_id, ax.libelle, count(DISTINCT t.valeur) AS valeurs,
       count(mt.comm_id) AS usages
  FROM axe ax LEFT JOIN tag t USING (axe_id)
  LEFT JOIN comm_tag mt USING (tag_id)
 GROUP BY ax.axe_id ORDER BY usages DESC;`,
          "⚠ count(mt.comm_id) balaye toute la table de liaison : acceptable sur un écran " +
          "d'administration ouvert une fois par mois, à surveiller si on l'affiche ailleurs", true],
        canaux: ["Administration — canaux d'entrée",
`-- en V1 il n'y a qu'un canal, et c'est justement le moment de le dire
SELECT canal, count(*) FROM comm GROUP BY canal;   -- ('email', 4412)`,
          "⚠ écrire cette colonne dès la V1 coûte un octet par message ; l'ajouter en V4 " +
          "coûte une migration sur des dizaines de millions de lignes et la relecture de " +
          "toutes les requêtes. Même raisonnement que D062 : on ne construit pas, on ne se " +
          "ferme pas la porte", true],
        suite: ["Administration — fournisseurs de la suite",
`SELECT cle, valeur FROM configuration
 WHERE organisation_id = :org AND cle LIKE 'capacite.%';`,
          "quatre lignes de configuration décident si AtomBox est une suite autonome ou un " +
          "webmail branché sur l'existant — et aucune vue n'en dépend"],
      }[volet];
      if (L) ABX.log(L[0], L[1], L[2], L[3]);
    },

    geste(code) {
      const [quoi, arg] = code.split(":");
      const G = {
        boite: ["Créer une boîte",
`INSERT INTO boite (domaine_id, adresse, type, quota_octets)
VALUES (:domaine, :adresse, 'personnelle', :quota) RETURNING boite_id;
-- les dossiers SPECIAL-USE sont créés en même temps, et protégés (D047)
INSERT INTO dossier (boite_id, nom, special_use, protege)
SELECT :boite, x.nom, x.usage, true
  FROM (VALUES ('INBOX',NULL),('Sent','\\\\Sent'),('Drafts','\\\\Drafts'),
               ('Junk','\\\\Junk'),('Trash','\\\\Trash')) AS x(nom, usage);`,
          "créer une boîte, c'est créer ses dossiers spéciaux dans la même transaction : un " +
          "client IMAP qui ne trouve pas \\\\Sent en invente un, et le courrier se disperse"],
        alias: ["Créer un alias",
`INSERT INTO boite (domaine_id, adresse, type, alias_de)
VALUES (:domaine, :adresse, 'alias', :cible);`,
          "l'alias a sa propre boîte_id : un message qui lui est adressé sait qu'il l'était " +
          "(D039), là où une simple redirection perdrait cette information à jamais"],
        app: ["Connecter une application",
`INSERT INTO application (code, libelle, type) VALUES (:code, :libelle, :type)
RETURNING application_id;
INSERT INTO jeton (application_id, empreinte, portee, expire_le)
VALUES (:app, sha256(:secret), :portee, now() + interval '1 year');`,
          "⚠ le secret n'est montré QU'UNE FOIS, à la création : on n'en garde que l'empreinte. " +
          "C'est contraignant à l'usage, et c'est la seule façon qu'une fuite de base ne " +
          "donne pas accès aux boîtes", true],
        tok: ["Révoquer et régénérer le jeton de « " + arg + " »",
`UPDATE jeton SET revoque_le = now() WHERE application_id = :app AND revoque_le IS NULL;
INSERT INTO jeton (application_id, empreinte, portee, expire_le)
VALUES (:app, sha256(:nouveau), :portee, now() + interval '1 year');`,
          "révoquer ne touche PAS aux tags déjà posés : ils appartiennent à l'application, pas " +
          "au jeton. Une révocation coupe l'accès, elle ne réécrit pas l'histoire (D020)"],
        axe: ["Créer un axe",
`INSERT INTO axe (axe_id, libelle, type_valeur) VALUES (:id, :libelle, 'texte');
INSERT INTO acl_axe (axe_id, principal, droit) VALUES (:id, :moi, 'administrer');`,
          "⚠ Q005 : le mécanisme existe, la politique non. Qui a le droit de créer un axe décide " +
          "de l'interopérabilité de toute l'installation", true],
      }[quoi];
      if (G) ABX.log(G[0], G[1], G[2], G[3]);
    },

    /* ---- pièces jointes ---------------------------------------------- */
    peindrePJ() {
      /* les liaisons arrivent par la couche d'accès (D141) : au premier passage on
         charge, on peint l'attente, et on repeint à la réponse */
      if (!ABX.Views.Attachments.charge) {
        D.paint("detail", `<div class="empty">Chargement des pièces jointes…</div>`);
        return ABX.Api.piecesJointes().then(l => { ABX.Views.Attachments.charger(l); Admin.peindrePJ(); });
      }
      const el = D.paint("detail", ABX.Views.Attachments.render(St.ui));
      ABX.Controllers.App.bindRetour(el);
      const liste = () => ABX.Views.Attachments.filtrer(St.ui.pjq, St.ui.pjtype);

      const q = el.querySelector("#pjq");
      q.oninput = e => { St.ui.pjq = e.target.value; const p = e.target.selectionStart;
        Admin.peindrePJ(); const i2 = D.byId("pjq"); i2.focus(); i2.setSelectionRange(p, p);
        if (St.ui.pjq.length === 3) ABX.log("Chercher une pièce jointe",
`SELECT l.nom_fichier, p.octets, p.mime_detecte, m.sujet, m.date_reception
  FROM comm_piece_jointe l
  JOIN piece_jointe p USING (pj_id)
  JOIN comm m USING (comm_id)
  JOIN rattachement r ON r.comm_id = m.comm_id AND r.compte_id = :moi
 WHERE l.nom_fichier ILIKE '%' || :q || '%'
 ORDER BY m.date_reception DESC LIMIT 60;`,
          "⚠ ILIKE '%…%' ne s'indexe pas : il faut un index trigramme (pg_trgm) sur " +
          "nom_fichier, ou accepter un balayage. À 4 millions de liaisons, ce n'est plus " +
          "un détail — et c'est le seul écran du POC qui cherche du TEXTE hors du corps", true);
      };

      D.on(el, ".chip[data-pjt]", "onclick", c => { St.ui.pjtype = c.dataset.pjt;
                                                    Admin.peindrePJ(); });
      D.on(el, ".pjname", "onchange", inp => {
        const x = liste()[+inp.dataset.k]; if (!x) return;
        Admin.renommer(x, inp.value);
      });
      D.on(el, "[data-pja]", "onclick", b => {
        const x = liste()[+b.dataset.k]; if (!x) return;
        if (b.dataset.pja === "ouvrir")
          return ABX.Controllers.Tabs.ouvrir({ type:"msg", id:x.m.id }, false);
        if (b.dataset.pja === "deposer") return ABX.Capacites.deposerFichier(x.m, x.i);
        ABX.log("Taguer une pièce jointe",
`INSERT INTO fichier_tag (pj_id, comm_id, axe_id, valeur, pose_par)
VALUES (${x.b.pj_id}, '${x.m.id}', :axe, :valeur, :moi)
ON CONFLICT DO NOTHING;`,
          "le tag porte (pj_id, comm_id) et non pj_id seul : deux messages partagent l'octet " +
          "mais pas forcément le classement — la même facture peut être « à payer » chez l'un " +
          "et « archivée » chez l'autre");
      });
    },

    renommer(x, nom) {
      if (!nom.trim() || nom === x.p.nom) return;
      const ancien = x.p.nom;
      x.p.nom = nom.trim();
      St.patch(x.m, { pieces_jointes: x.m.pieces_jointes });
      St.save();
      ABX.log({ label:"Renommer « " + ancien + " » en « " + x.p.nom + " »", etapes:[
        { t:"ui", label:"saisie dans la liste des pièces jointes",
          detail:"views/attachments.js → Controllers.Admin.renommer" },
        { t:"http", label:"c'est la LIAISON qu'on modifie, pas le fichier",
          detail:"PATCH /api/v1/messages/" + x.m.id + "/pieces-jointes/" + x.b.pj_id +
                 "\n{ \"nom_fichier\": \"" + x.p.nom + "\" }" },
        { t:"sql", label:"une seule liaison change",
          detail:
`UPDATE comm_piece_jointe SET nom_fichier = :nom
 WHERE comm_id = '${x.m.id}' AND pj_id = ${x.b.pj_id};`,
          index:"le blob n'est pas touché : les " + (x.b.refs - 1) + " autre(s) liaison(s) " +
                "gardent leur nom, et le message d'origine reste reconstructible à l'identique " +
                "(D025/D032). C'est la seule forme de renommage qui ne casse pas DKIM" },
        { t:"note", label:"ce qu'on ne peut pas faire",
          detail:"renommer le fichier « partout »",
          index:"⚠ il n'y a pas de « partout » : un octet n'a pas de nom, seules les liaisons " +
                "en ont. Un utilisateur qui attend l'inverse sera surpris — l'écran doit le dire",
          warn:true },
      ]});
      ABX.Bus.emit("corpus:changed", {});
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Admin = Admin;
})(window.ABX = window.ABX || {});
