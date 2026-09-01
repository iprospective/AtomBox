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
    if (log) ABX.log(...(Array.isArray(log) ? log : [log]));
    ABX.Bus.emit("corpus:changed", { message: m, patch });
  }

  const M = {
    appliquer,

    lire: m => appliquer(m, { lu: true }, ["Marquer lu",
`UPDATE rattachement SET lu_le = now()
 WHERE message_id = :id AND compte_id = :moi AND lu_le IS NULL;`,
      "une ÉCRITURE à chaque ouverture — le prix d'un compteur de non-lus juste, et d'un début " +
      "de workflow de traitement (D41). Le IS NULL évite de réécrire une ligne déjà lue"]),

    nonLu: m => appliquer(m, { lu: false }, ["Marquer non lu",
`UPDATE rattachement SET lu_le = NULL WHERE message_id = :id AND compte_id = :moi;`,
      "le compteur redevient juste sans toucher au journal : la lecture reste tracée dans " +
      "activite, on n'efface pas un fait (D54/D59)"]),

    traiter: m => appliquer(m, { motif:"traite", sorti: Date.now() }, {
      label: "Marquer traité", warn: true,
      index: "deux écritures pour un clic : l'état courant d'un côté, le fait daté de l'autre. " +
             "Confondre les deux, c'est perdre l'historique au premier changement d'avis",
      enfants: [
        { label: "l'état : le message quitte la file",
          sql:
`UPDATE rattachement SET sorti_le = now(), motif_sortie = 'traite'
 WHERE message_id = :id AND compte_id = :moi;`,
          index: "⚠ déplace la ligne de partition si sorti_le en est la clé (D14/D30) — un seul " +
                 "déplacement par email, c'est le pari de la conception", warn: true },
        { label: "le fait : « a traité », daté, non modifiable",
          sql:
`INSERT INTO activite (compte_id, message_id, type, at) VALUES (:moi, :id, 'traite', now());`,
          index: "le journal est partitionné par année (D56) : il grossit sans fin, mais on ne " +
                 "lit jamais que le haut" },
      ] }),

    archiver: m => appliquer(m, { motif:"archive", sorti: Date.now() }, ["Archiver (sortir sans traiter)",
`UPDATE rattachement SET sorti_le = now(), motif_sortie = 'archive'
 WHERE message_id = :id AND compte_id = :moi;`,
      "motif_sortie distingue traité / archivé (D30) ; les vues « Traités » et « Archives » " +
      "n'en sont que la lecture (D51)"]),

    refile: m => appliquer(m, { motif:null, sorti:null }, ["Remettre dans la file",
`UPDATE rattachement SET sorti_le = NULL, motif_sortie = NULL
 WHERE message_id = :id AND compte_id = :moi;`,
      "⚠ retour de partition : c'est exactement Q09 (« un email sorti peut-il revenir ? »). " +
      "Autorisé ici — reste à décider si le cas est courant ou exceptionnel, la réponse " +
      "change le partitionnement", true]),

    corbeille: m => appliquer(m, { dossier:"trash" }, ["Mettre à la corbeille",
`UPDATE rattachement SET dossier_id = :trash, deplace_le = now()
 WHERE message_id = :id AND compte_id = :moi;`,
      "la corbeille est un DÉPLACEMENT, pas une suppression : le message est intact et les " +
      "autres comptes qui le portent ne voient rien (D10)"]),

    junk: m => appliquer(m, { dossier:"junk" }, {
      label: "Marquer indésirable",
      index: "sans la seconde écriture, l'utilisateur reclasse à la main indéfiniment : le " +
             "classement range, l'apprentissage évite d'avoir à ranger (D71)",
      enfants: [
        { label: "le message part en quarantaine",
          sql: `UPDATE rattachement SET dossier_id = :junk
 WHERE message_id = :id AND compte_id = :moi;`,
          index: "la quarantaine est un dossier comme un autre — ce qui la distingue est sa " +
                 "purge automatique, à décider" },
        { label: "le filtre apprend",
          sql:
`INSERT INTO apprentissage_spam (message_id, verdict, par, at)
VALUES (:id, 'spam', :moi, now());`,
          index: "verdict par UTILISATEUR, pas global : ce que l'un juge indésirable, l'autre " +
                 "l'attend — un apprentissage partagé sur une boîte commune se retourne vite" },
      ] }),

    restaurer: m => appliquer(m, { dossier:null }, ["Restaurer depuis la corbeille",
`UPDATE rattachement SET dossier_id = :origine WHERE message_id = :id AND compte_id = :moi;`,
      "il faut donc conserver le dossier d'origine : une corbeille sans retour n'est qu'une " +
      "suppression déguisée"]),

    supprimer: m => appliquer(m, { suppr: true }, {
      label: "Supprimer définitivement", warn: true,
      index: "⚠ un message dédupliqué appartient à plusieurs comptes (D10) : « supprimer » du " +
             "point de vue d'un utilisateur n'est jamais un DELETE du message",
      enfants: [
        { label: "ce que le clic fait vraiment, tout de suite",
          sql: `DELETE FROM rattachement WHERE message_id = :id AND compte_id = :moi;`,
          index: "immédiat, indexé, sans effet sur les autres porteurs" },
        { label: "ce que le ramasse-miettes fera plus tard, si personne ne le porte plus (D87)",
          sql:
`DELETE FROM message m WHERE m.message_id = :id AND NOT EXISTS
  (SELECT 1 FROM rattachement r WHERE r.message_id = m.message_id);`,
          index: "⚠ jamais dans le clic : c'est un balayage, pas une cascade ON DELETE", warn: true },
      ] }),

    deplacer: (m, dest) => appliquer(m, { dossier: dest || null }, ["Déplacer vers un dossier",
`UPDATE rattachement SET dossier_id = :dossier WHERE message_id = :id AND compte_id = :moi;`,
      "le dossier utilisateur est une colonne du RATTACHEMENT, pas du message : deux comptes " +
      "classent le même message différemment (D51/D36)"]),

    nonJunk: m => appliquer(m, { dossier: null }, {
      label: "« Ce n'est pas un indésirable »",
      index: "un filtre qui n'apprend que dans un sens dérive (D71) — et c'est la seule trace " +
             "qui permettra de mesurer le taux de faux positifs de la quarantaine",
      enfants: [
        { label: "retour au dossier d'origine",
          sql: `UPDATE rattachement SET dossier_id = :origine
 WHERE message_id = :id AND compte_id = :moi;`,
          index: "d'où la nécessité de D88 : sans dossier d'origine mémorisé, on ne sait pas où " +
                 "le remettre" },
        { label: "le filtre désapprend",
          sql:
`INSERT INTO apprentissage_spam (message_id, verdict, par, at)
VALUES (:id, 'ham', :moi, now());` },
      ] }),

    /* Les tags sont posés sur le MESSAGE, pas sur le rattachement (D17) : c'est ce
       qui les rend interopérables entre applications. Un tag posé par un connecteur
       et retiré à la main sera reposé au passage suivant — l'écran doit le dire. */
    ajouterTag(m, axe, val) {
      if (!axe || !val.trim()) return;
      const v = val.trim();
      if (m.tags.some(t => t.axe === axe && t.val === v)) return;
      appliquer(m, { tags: m.tags.concat([{ axe, val: v, src: "utilisateur" }]) },
        { label: "Poser le tag " + axe + " = " + v,
          index: "le droit d'écrire sur l'axe est vérifié en amont (D18) — poser un tag sur un " +
                 "axe qu'on ne peut que lire doit être refusé, pas ignoré",
          enfants: [
            { label: "le tag existe-t-il déjà pour cette application ?",
              sql:
`INSERT INTO tag (axe_id, application_id, valeur)
VALUES (:axe, :moi_application, :valeur)
ON CONFLICT (axe_id, application_id, valeur) DO NOTHING
RETURNING tag_id;`,
              index: "unicité (axe, application, valeur) — D20 ; ici l'application est " +
                     "l'utilisateur lui-même, qui en est une comme les autres" },
            { label: "la liaison",
              sql:
`INSERT INTO message_tag (message_id, tag_id, pose_par, pose_le)
VALUES (:id, :tag, :moi, now()) ON CONFLICT DO NOTHING;`,
              index: "pas d'unicité (message, axe) : un message peut relever de deux clients (D17)" },
          ] });
    },

    retirerTag(m, i) {
      const t = m.tags[i];
      if (!t) return;
      const auto = t.src && t.src !== "utilisateur";
      appliquer(m, { tags: m.tags.filter((_, k) => k !== i) },
        ["Retirer le tag " + t.axe + " = " + t.val,
`DELETE FROM message_tag
 WHERE message_id = :id AND tag_id = :tag AND pose_par = :moi;

-- le tag lui-même n'est PAS supprimé : d'autres messages le portent`,
          auto
            ? "⚠ ce tag a été posé par « " + t.src + " » : le retirer ici ne l'empêche pas " +
              "d'être reposé au prochain passage du connecteur. Un retrait durable suppose " +
              "soit une table d'exclusions, soit un retrait côté application (D19/D21)"
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
        index: "⚠ la déduplication impose un RAMASSE-MIETTES (D87) : un seul de ces trois " +
               "étages appartient au clic, les deux autres sont des balayages",
        enfants: [
          { label: "1. immédiat — on ne supprime pas le message, mais le rattachement",
            sql: `DELETE FROM rattachement WHERE compte_id = :moi AND dossier_id = :trash;`,
            index: "index (compte_id, dossier_id) — borné au compte, donc instantané" },
          { label: "2. tâche de fond — le message ne part que si plus personne ne le porte (D10)",
            sql:
`DELETE FROM message m WHERE NOT EXISTS
  (SELECT 1 FROM rattachement r WHERE r.message_id = m.message_id);`,
            index: "⚠ balayage de toute la table : à faire par lots, jamais dans le clic", warn: true },
          { label: "3. tâche de fond — le blob, que si plus aucune liaison ne le cite (D24)",
            sql:
`DELETE FROM piece_jointe p WHERE NOT EXISTS
  (SELECT 1 FROM message_piece_jointe l WHERE l.pj_id = p.pj_id);`,
            index: "⚠ idem, plus le retrait des octets du magasin — qui n'est pas transactionnel", warn: true },
        ] });
      ABX.Bus.emit("corpus:changed", {});
    },
  };

  ABX.MessageService = M;
})(window.ABX = window.ABX || {});
