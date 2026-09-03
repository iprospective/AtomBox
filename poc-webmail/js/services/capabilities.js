/* LES GESTES DES CAPACITÉS — créer une tâche, ouvrir une fiche, déposer un fichier.

   Une seule intention par geste ; le fournisseur branché décide de ce qui se
   passe. Le POC ne fabrique pas de tâches ni de contacts : il montre la cascade,
   parce que c'est elle qui diffère et c'est elle qu'il faut comparer. */
(function (ABX) {
  "use strict";
  const P = () => ABX.Providers, T = () => ABX.Traces, F = ABX.Fmt;

  const j = o => JSON.stringify(o, null, 2);
  const echeance = () => new Date(Date.now() + 3 * 864e5).toISOString().slice(0, 10);

  const Capacites = {
    resoudre: cap => P().actif(cap),

    /* ---- créer une tâche depuis un message ------------------------------ */
    creerTache(m) {
      T().capacite("taches", "Créer une tâche", m,
        () => [
          { t:"sql", label:"une table, une clé étrangère",
            detail:
`INSERT INTO tache (compte_id, titre, echeance, comm_id, statut)
VALUES (:moi, :titre, :echeance, '` + m.id + `', 'a_faire')
RETURNING tache_id;`,
            index:"le lien avec le message est une CLÉ ÉTRANGÈRE, pas une URL : il ne peut pas " +
                  "pointer dans le vide, et supprimer le message force à décider du sort de la tâche" },
          { t:"sql", label:"et la file de travail devient une seule requête",
            detail:
`SELECT t.*, m.sujet FROM tache t
  LEFT JOIN comm m USING (comm_id)
 WHERE t.compte_id = :moi AND t.statut <> 'faite'
 ORDER BY t.echeance NULLS LAST;`,
            index:"index (compte_id, statut, echeance) — c'est le seul cas où « à faire » et " +
                  "« emails à traiter » se lisent ensemble sans appel externe" },
        ],
        f => [
          { t:"http", label:"la tâche est créée CHEZ LUI",
            detail:"POST https://" + f.base + ".lan" + f.endpoint + "\n" +
              j({ label: m.subject, dateo: echeance(),
                  note: "Depuis AtomBox — message " + m.id,
                  fk_project: null, atombox_comm_id: m.id }),
            index:"AtomBox ne stocke rien de la tâche : au retour, il ne garde qu'une " +
                  "référence externe (D84)" },
          { t:"json", label:"201 — l'identifiant qui servira de lien",
            detail: j({ id: 4821, ref: "TASK4821",
                        url: "https://" + f.base + ".lan/projet/task/card.php?id=4821" }) },
          { t:"sql", label:"seul le lien entre dans AtomBox",
            detail:
`INSERT INTO objet_lie (comm_id, application_id, type, ref_externe, url)
VALUES ('` + m.id + `', :app, 'tache', :ref, :url);`,
            index:"⚠ ce lien peut mourir : la tâche est supprimable chez le fournisseur sans " +
                  "qu'AtomBox le sache. Même problème que Q30 sur le transfert par référence — " +
                  "il faut afficher un lien mort, pas un vide silencieux",
            warn:true },
          { t:"note", label:"et la file de travail ?",
            detail:"elle demande un appel de plus, à chaque affichage",
            index:"⚠ « mes emails à traiter » et « mes tâches » ne se lisent plus dans la même " +
                  "requête : c'est le prix du fournisseur externe, et c'est Q31 qui revient",
            warn:true },
        ]);
    },

    /* ---- ouvrir la fiche du correspondant ------------------------------- */
    ficheContact(m) {
      T().capacite("contacts", "Fiche du correspondant", m,
        () => [
          { t:"sql", label:"la table existe déjà — c'est D35",
            detail:
`SELECT c.correspondant_id, c.libelle,
       array_agg(a.adresse ORDER BY a.principale DESC) AS adresses
  FROM adresse a JOIN correspondant c USING (correspondant_id)
 WHERE c.correspondant_id = (SELECT correspondant_id FROM adresse
                              WHERE adresse = lower('` + m.mail + `'))
 GROUP BY c.correspondant_id;`,
            index:"le contact natif n'est pas une fonctionnalité de plus : c'est l'affichage " +
                  "de l'identité multi-adresses dont AtomBox a déjà besoin pour rattacher" },
          { t:"sql", label:"et tout son historique, sans quitter la base",
            detail:
`SELECT m.comm_id, m.sujet, m.date_reception, r.sens
  FROM adresse a
  JOIN comm m ON m.from_adresse = a.adresse OR :moi = ANY (m.to_adresses)
  JOIN rattachement r USING (comm_id)
 WHERE a.correspondant_id = :cid AND r.compte_id = :moi
 ORDER BY m.date_reception DESC LIMIT 50;`,
            index:"⚠ ce OR est le piège : il faut une table de participation " +
                  "(comm_id, adresse, role) pour que cette requête s'indexe", warn:true },
        ],
        f => [
          { t:"http", label:"recherche par adresse chez le fournisseur",
            detail: f.id === "carddav"
              ? "REPORT " + f.endpoint + "\n<C:addressbook-query><C:filter>\n" +
                "  <C:prop-filter name=\"EMAIL\"><C:text-match>" + m.mail + "</C:text-match>\n" +
                "</C:filter></C:addressbook-query>"
              : "GET https://" + f.base + ".lan" + f.endpoint + "?sqlfilters=(email:=:'" + m.mail + "')",
            index: f.id === "carddav"
              ? "une requête CardDAV par message affiché : à mettre en cache, ou à précharger " +
                "l'annuaire entier au démarrage"
              : "l'ERP répond le tiers ET son encours : un seul appel pour la fiche et le contexte" },
          { t:"json", label:"la fiche, telle que le fournisseur la voit",
            detail: f.id === "carddav"
              ? "BEGIN:VCARD\nFN:" + m.from + "\nEMAIL;TYPE=work:" + m.mail + "\nUID:…\nEND:VCARD"
              : j({ id: 1042, name: m.from, email: m.mail, client: 1 }) },
          { t:"note", label:"ce qu'AtomBox perd en déléguant",
            detail:"l'identité multi-adresses de D35 doit être reconstruite à chaque appel",
            index: f.id === "carddav"
              ? "⚠ une vCard porte plusieurs EMAIL, mais rien ne garantit que deux vCards ne " +
                "partagent pas une adresse — le rattachement automatique devient ambigu"
              : "l'ERP fait autorité sur ses tiers : c'est un avantage tant qu'un correspondant " +
                "n'est pas un tiers (candidat, prestataire ponctuel, robot)",
            warn: f.id === "carddav" },
        ]);
    },

    /* ---- déposer une pièce jointe dans le gestionnaire de fichiers ------- */
    deposerFichier(m, i) {
      const p = m.pjs[i]; if (!p) return;
      T().capacite("fichiers", "Enregistrer « " + p.nom + " »", m,
        () => [
          { t:"sql", label:"l'octet est déjà là — on pose un classement, pas une copie",
            detail:
`INSERT INTO fichier (pj_id, compte_id, nom, dossier, tags)
VALUES (` + p.b.pj_id + `, :moi, :nom, :dossier, :tags)
ON CONFLICT (pj_id, compte_id) DO UPDATE SET nom = EXCLUDED.nom;`,
            index:"« enregistrer » ne copie RIEN (D24) : le blob de " + F.poids(p.b.ko) +
                  " est déjà stocké et partagé par " + p.b.refs + " liaison(s). C'est la " +
                  "démonstration la plus nette de l'intérêt du magasin dédupliqué" },
        ],
        f => [
          { t:"blob", label:"il faut d'abord relire l'octet",
            detail:"zstd -d blob/" + p.b.sha.slice(0, 2) + "/" + p.b.sha,
            index:"le fichier ne peut pas être transféré par référence : le fournisseur veut " +
                  "les octets" },
          { t:"http", label:"dépôt WebDAV — " + F.poids(p.b.ko) + " sur le réseau",
            detail:"PUT https://" + f.base + ".lan" + f.endpoint + "Emails/" + p.nom +
                   "\nContent-Type: " + p.b.mime + "\nContent-Length: " + (p.b.ko * 1024),
            index:"⚠ l'octet existe maintenant DEUX fois — une dans le magasin d'AtomBox, une " +
                  "chez Nextcloud — et la déduplication ne protège plus ce second exemplaire. " +
                  "C'est le coût assumé de la délégation, pas un défaut d'implémentation",
            warn:true },
          { t:"sql", label:"AtomBox ne garde que le lien",
            detail:
`INSERT INTO objet_lie (comm_id, application_id, type, ref_externe, url)
VALUES ('` + m.id + `', :app, 'fichier', :chemin, :url);` },
        ]);
    },
  };

  ABX.Capacites = Capacites;
})(window.ABX = window.ABX || {});
