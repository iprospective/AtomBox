/* SERVICE MÉTIER — les gestes sur un message.

   Chaque action fait trois choses, toujours dans cet ordre : elle mute l'état,
   elle journalise la requête qu'elle aurait écrite en base, elle émet. Aucune
   vue n'est appelée d'ici : c'est le contrôleur qui décide quoi repeindre. */
(function (ABX) {
  "use strict";
  const St = ABX.Store, C = ABX.Corpus;

  function appliquer(m, patch, log) {
    St.patch(m, patch);
    if (patch.suppr) C.retire(m);
    C.recompte();
    St.save();
    if (typeof log === "function") log(m);
    else if (log) ABX.log(...(Array.isArray(log) ? log : [log]));
    ABX.Bus.emit("corpus:changed", { message: m, patch });
  }

  const M = {
    appliquer,

    /* `muet` : l'ouverture d'un message décrit déjà cette écriture dans sa
       cascade — inutile de la journaliser deux fois. */
    lire: (m, muet) => appliquer(m, { lu: true }, muet ? null : ["Marquer lu",
`UPDATE rattachement SET lu_le = now()
 WHERE comm_id = :id AND compte_id = :moi AND lu_le IS NULL;`,
      "une ÉCRITURE à chaque ouverture — le prix d'un compteur de non-lus juste, et d'un début " +
      "de workflow de traitement (D041). Le IS NULL évite de réécrire une ligne déjà lue"]),

    nonLu: m => appliquer(m, { lu: false }, ["Marquer non lu",
`UPDATE rattachement SET lu_le = NULL WHERE comm_id = :id AND compte_id = :moi;`,
      "le compteur redevient juste sans toucher au journal : la lecture reste tracée dans " +
      "activite, on n'efface pas un fait (D054/D059)"]),

    traiter: m => appliquer(m, { motif:"traite", sorti: Date.now() },
      x => ABX.Traces.muter(x, {
        label:"Marquer traité", nom:"traiter",
        corps:{ sorti: true, motif_sortie: "traite" },
        retour:{ comm_id: x.id, sorti_le: "2026-09-01T14:02:11+02:00",
                 motif_sortie: "traite", lu_le: "2026-09-01T14:01:58+02:00" },
      }, [
        { t:"sql", label:"l'état : le message quitte la file",
          detail:
`UPDATE rattachement SET sorti_le = now(), motif_sortie = 'traite'
 WHERE comm_id = :id AND compte_id = :moi;`,
          index:"⚠ si sorti_le est la clé de partition (D014/D030), cet UPDATE n'écrit pas une " +
                "ligne : il la DÉPLACE — suppression dans une partition, insertion dans une " +
                "autre. Le pari « un seul déplacement par email » tient tant que Q009 reste rare",
          warn:true },
        { t:"sql", label:"le fait : « a traité », daté, non modifiable",
          detail:
`INSERT INTO activite (compte_id, comm_id, type, at)
VALUES (:moi, :id, 'traite', now());`,
          index:"deux écritures pour un clic, et c'est voulu : l'état courant d'un côté, le fait " +
                "daté de l'autre. Les confondre, c'est perdre l'historique au premier changement " +
                "d'avis (D054). Journal partitionné par année (D056)" },
        { t:"event", label:"les applications connectées sont prévenues",
          detail:
`INSERT INTO evenement_sortant (application_id, type, charge, etat, prochaine_tentative)
SELECT application_id, 'message.traite', :json, 'a_emettre', now()
  FROM abonnement WHERE type = 'message.traite';`,
          index:"un ERP qui suit ses échanges veut savoir qu'un message a été traité — mais " +
                "l'apprendre ne doit pas retarder le clic (D086)" },
      ])),

    archiver: m => appliquer(m, { motif:"archive", sorti: Date.now() }, ["Archiver (sortir sans traiter)",
`UPDATE rattachement SET sorti_le = now(), motif_sortie = 'archive'
 WHERE comm_id = :id AND compte_id = :moi;`,
      "motif_sortie distingue traité / archivé (D030) ; les vues « Traités » et « Archives » " +
      "n'en sont que la lecture (D051)"]),

    refile: m => appliquer(m, { motif:null, sorti:null }, ["Remettre dans la file",
`UPDATE rattachement SET sorti_le = NULL, motif_sortie = NULL
 WHERE comm_id = :id AND compte_id = :moi;`,
      "⚠ retour de partition : c'est exactement Q009 (« un email sorti peut-il revenir ? »). " +
      "Autorisé ici — reste à décider si le cas est courant ou exceptionnel, la réponse " +
      "change le partitionnement", true]),

    corbeille: m => appliquer(m, { dossier:"trash" },
      x => ABX.Traces.muter(x, {
        label:"Mettre à la corbeille", nom:"corbeille",
        corps:{ dossier: "trash" },
        retour:{ comm_id: x.id, dossier_id: "trash",
                 dossier_origine: (x.fid || "inbox"), deplace_le: "2026-09-01T14:02:11+02:00" },
      }, [
        { t:"sql", label:"un déplacement, pas une suppression",
          detail:
`UPDATE rattachement
   SET dossier_origine = COALESCE(dossier_origine, dossier_id),
       dossier_id = :trash, deplace_le = now()
 WHERE comm_id = :id AND compte_id = :moi;`,
          index:"le message est intact, et les autres comptes qui le portent ne voient rien (D010). " +
                "COALESCE : on mémorise l'origine au PREMIER passage seulement, sinon un " +
                "aller-retour corbeille ferait de la corbeille l'origine (D088)" },
        { t:"note", label:"ce qui ne se passe PAS ici",
          detail:"aucun DELETE, aucun ramasse-miettes, aucune touche au magasin d'octets",
          index:"la suppression réelle est un balayage, jamais un clic (D087) — c'est « vider la " +
                "corbeille » qui la déclenche, et encore, en tâche de fond" },
      ])),

    junk: m => appliquer(m, { dossier:"junk" }, {
      label: "Marquer indésirable",
      index: "sans la seconde écriture, l'utilisateur reclasse à la main indéfiniment : le " +
             "classement range, l'apprentissage évite d'avoir à ranger (D071)",
      enfants: [
        { label: "le message part en quarantaine",
          sql: `UPDATE rattachement SET dossier_id = :junk
 WHERE comm_id = :id AND compte_id = :moi;`,
          index: "la quarantaine est un dossier comme un autre — ce qui la distingue est sa " +
                 "purge automatique, à décider" },
        { label: "le filtre apprend",
          sql:
`INSERT INTO apprentissage_spam (comm_id, verdict, par, at)
VALUES (:id, 'spam', :moi, now());`,
          index: "verdict par UTILISATEUR, pas global : ce que l'un juge indésirable, l'autre " +
                 "l'attend — un apprentissage partagé sur une boîte commune se retourne vite" },
      ] }),

    restaurer: m => appliquer(m, { dossier:null }, ["Restaurer depuis la corbeille",
`UPDATE rattachement SET dossier_id = :origine WHERE comm_id = :id AND compte_id = :moi;`,
      "il faut donc conserver le dossier d'origine : une corbeille sans retour n'est qu'une " +
      "suppression déguisée"]),

    supprimer: m => appliquer(m, { suppr: true }, {
      label: "Supprimer définitivement", warn: true,
      index: "⚠ un message dédupliqué appartient à plusieurs comptes (D010) : « supprimer » du " +
             "point de vue d'un utilisateur n'est jamais un DELETE du message",
      enfants: [
        { label: "ce que le clic fait vraiment, tout de suite",
          sql: `DELETE FROM rattachement WHERE comm_id = :id AND compte_id = :moi;`,
          index: "immédiat, indexé, sans effet sur les autres porteurs" },
        { label: "ce que le ramasse-miettes fera plus tard, si personne ne le porte plus (D087)",
          sql:
`DELETE FROM comm m WHERE m.comm_id = :id AND NOT EXISTS
  (SELECT 1 FROM rattachement r WHERE r.comm_id = m.comm_id);`,
          index: "⚠ jamais dans le clic : c'est un balayage, pas une cascade ON DELETE", warn: true },
      ] }),

    deplacer: (m, dest) => appliquer(m, { dossier: dest || null }, ["Déplacer vers un dossier",
`UPDATE rattachement SET dossier_id = :dossier WHERE comm_id = :id AND compte_id = :moi;`,
      "le dossier utilisateur est une colonne du RATTACHEMENT, pas du message : deux comptes " +
      "classent le même message différemment (D051/D036)"]),

    nonJunk: m => appliquer(m, { dossier: null }, {
      label: "« Ce n'est pas un indésirable »",
      index: "un filtre qui n'apprend que dans un sens dérive (D071) — et c'est la seule trace " +
             "qui permettra de mesurer le taux de faux positifs de la quarantaine",
      enfants: [
        { label: "retour au dossier d'origine",
          sql: `UPDATE rattachement SET dossier_id = :origine
 WHERE comm_id = :id AND compte_id = :moi;`,
          index: "d'où la nécessité de D088 : sans dossier d'origine mémorisé, on ne sait pas où " +
                 "le remettre" },
        { label: "le filtre désapprend",
          sql:
`INSERT INTO apprentissage_spam (comm_id, verdict, par, at)
VALUES (:id, 'ham', :moi, now());` },
      ] }),

    /* Le workflow de traitement. « Traité » sort de la file — les autres états
       sont des positions DANS la file, pas des sorties. */
    statuer(m, id) {
      const st = ABX.Fixtures.statut(id);
      const patch = { statut: id };
      if (st.sortie) { patch.motif = st.sortie; patch.sorti = Date.now(); }
      else if (m.motif === "traite") { patch.motif = null; patch.sorti = null; }
      appliquer(m, patch, x => ABX.Traces.muter(x, {
        label:"Statut : " + st.label, nom:"statuer",
        corps:{ statut: id },
        retour:{ comm_id: x.id, statut: id,
                 sorti_le: st.sortie ? "2026-09-01T14:02:11+02:00" : null,
                 motif_sortie: st.sortie || null },
      }, [
        { t:"sql", label:"une colonne, pas une ligne de plus",
          detail:
`UPDATE rattachement SET statut = :statut` + (st.sortie
  ? `, sorti_le = now(), motif_sortie = '` + st.sortie + `'` : `, sorti_le = NULL, motif_sortie = NULL`) + `
 WHERE comm_id = :id AND compte_id = :moi;`,
          index: st.sortie
            ? "⚠ « traité » est le seul statut qui SORT de la file : il pose sorti_le, donc " +
              "déplace la partition (D014/D030). Les autres se contentent de bouger dans la file"
            : "statut est un ENUM ordonné sur le rattachement : fermé, donc indexable, et propre " +
              "au compte, donc deux personnes d'une boîte commune ont deux files (Q035)",
          warn: !!st.sortie },
        { t:"sql", label:"le changement d'état est un fait, comme la lecture",
          detail:
`INSERT INTO activite (compte_id, comm_id, type, detail, at)
VALUES (:moi, :id, 'statut', :statut, now());`,
          index:"c'est ce qui permettra de mesurer un délai de traitement — la seule métrique " +
                "que personne ne pense à stocker avant d'en avoir besoin" },
        { t:"note", label:"pourquoi pas un tag « à faire » ?",
          detail:"parce qu'un tag classe et qu'un statut pilote",
          index:"un tag est ouvert, interopérable et soumis à l'ACL d'un axe (D017/D018) : une " +
                "application connectée pourrait vider votre file de travail. Un statut est " +
                "fermé, ordonné, propre au compte — deux mécaniques, deux tables" },
      ]));
    },

    /* Les tags sont posés sur le MESSAGE, pas sur le rattachement (D017) : c'est ce
       qui les rend interopérables entre applications. Un tag posé par un connecteur
       et retiré à la main sera reposé au passage suivant — l'écran doit le dire. */
    ajouterTag(m, axe, val) {
      if (!axe || !val.trim()) return;
      const v = val.trim();
      if (m.tags.some(t => t.axe === axe && t.val === v)) return;
      appliquer(m, { tags: m.tags.concat([{ axe, val: v, src: "utilisateur" }]) },
        { label: "Poser le tag " + axe + " = " + v,
          index: "le droit d'écrire sur l'axe est vérifié en amont (D018) — poser un tag sur un " +
                 "axe qu'on ne peut que lire doit être refusé, pas ignoré",
          enfants: [
            { label: "le tag existe-t-il déjà pour cette application ?",
              sql:
`INSERT INTO tag (axe_id, application_id, valeur)
VALUES (:axe, :moi_application, :valeur)
ON CONFLICT (axe_id, application_id, valeur) DO NOTHING
RETURNING tag_id;`,
              index: "unicité (axe, application, valeur) — D020 ; ici l'application est " +
                     "l'utilisateur lui-même, qui en est une comme les autres" },
            { label: "la liaison",
              sql:
`INSERT INTO comm_tag (comm_id, tag_id, pose_par, pose_le)
VALUES (:id, :tag, :moi, now()) ON CONFLICT DO NOTHING;`,
              index: "pas d'unicité (message, axe) : un message peut relever de deux clients (D017)" },
          ] });
    },

    retirerTag(m, i) {
      const t = m.tags[i];
      if (!t) return;
      const auto = t.src && t.src !== "utilisateur";
      appliquer(m, { tags: m.tags.filter((_, k) => k !== i) },
        ["Retirer le tag " + t.axe + " = " + t.val,
`DELETE FROM comm_tag
 WHERE comm_id = :id AND tag_id = :tag AND pose_par = :moi;

-- le tag lui-même n'est PAS supprimé : d'autres messages le portent`,
          auto
            ? "⚠ ce tag a été posé par « " + t.src + " » : le retirer ici ne l'empêche pas " +
              "d'être reposé au prochain passage du connecteur. Un retrait durable suppose " +
              "soit une table d'exclusions, soit un retrait côté application (D019/D021)"
            : "le tag reste en base tant qu'un autre message le porte — supprimer la ligne de " +
              "liaison n'est pas supprimer le tag",
          auto]);
    },

    /* Vider la corbeille : le seul endroit où la déduplication se paie. */
    viderCorbeille(liste) {
      const n = liste.length;
      liste.slice().forEach(m => { St.patch(m, { suppr: true }); C.retire(m); });
      C.recompte(); St.save();
      ABX.log({
        label: "Vider la corbeille — " + n + " message(s)", warn: true,
        index: "⚠ la déduplication impose un RAMASSE-MIETTES (D087) : un seul de ces trois " +
               "étages appartient au clic, les deux autres sont des balayages",
        enfants: [
          { label: "1. immédiat — on ne supprime pas le message, mais le rattachement",
            sql: `DELETE FROM rattachement WHERE compte_id = :moi AND dossier_id = :trash;`,
            index: "index (compte_id, dossier_id) — borné au compte, donc instantané" },
          { label: "2. tâche de fond — le message ne part que si plus personne ne le porte (D010)",
            sql:
`DELETE FROM comm m WHERE NOT EXISTS
  (SELECT 1 FROM rattachement r WHERE r.comm_id = m.comm_id);`,
            index: "⚠ balayage de toute la table : à faire par lots, jamais dans le clic", warn: true },
          { label: "3. tâche de fond — le blob, que si plus aucune liaison ne le cite (D024)",
            sql:
`DELETE FROM piece_jointe p WHERE NOT EXISTS
  (SELECT 1 FROM comm_piece_jointe l WHERE l.pj_id = p.pj_id);`,
            index: "⚠ idem, plus le retrait des octets du magasin — qui n'est pas transactionnel", warn: true },
        ] });
      ABX.Bus.emit("corpus:changed", {});
    },
  };

  ABX.MessageService = M;
})(window.ABX = window.ABX || {});
