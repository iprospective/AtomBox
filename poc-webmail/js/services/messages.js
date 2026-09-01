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
    if (log) ABX.log(log[0], log[1], log[2], log[3]);
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

    traiter: m => appliquer(m, { motif:"traite", sorti: Date.now() }, ["Marquer traité",
`UPDATE rattachement SET sorti_le = now(), motif_sortie = 'traite'
 WHERE message_id = :id AND compte_id = :moi;
INSERT INTO activite (compte_id, message_id, type, at) VALUES (:moi, :id, 'traite', now());`,
      "⚠ déplace la ligne de partition si sorti_le en est la clé (D14/D30) — un seul déplacement " +
      "par email, c'est le pari de la conception", true]),

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

    junk: m => appliquer(m, { dossier:"junk" }, ["Marquer indésirable",
`UPDATE rattachement SET dossier_id = :junk WHERE message_id = :id AND compte_id = :moi;
INSERT INTO apprentissage_spam (message_id, verdict, par, at) VALUES (:id, 'spam', :moi, now());`,
      "le geste alimente la quarantaine ET l'apprentissage (D71) : sans la seconde ligne, " +
      "l'utilisateur reclasse à la main indéfiniment"]),

    restaurer: m => appliquer(m, { dossier:null }, ["Restaurer depuis la corbeille",
`UPDATE rattachement SET dossier_id = :origine WHERE message_id = :id AND compte_id = :moi;`,
      "il faut donc conserver le dossier d'origine : une corbeille sans retour n'est qu'une " +
      "suppression déguisée"]),

    supprimer: m => appliquer(m, { suppr: true }, ["Supprimer définitivement",
`DELETE FROM rattachement WHERE message_id = :id AND compte_id = :moi;
-- puis, en tâche de fond seulement :
DELETE FROM message m WHERE m.message_id = :id AND NOT EXISTS
  (SELECT 1 FROM rattachement r WHERE r.message_id = m.message_id);`,
      "⚠ un message dédupliqué appartient à plusieurs comptes (D10) : effacer le rattachement " +
      "n'efface pas le message, et le blob d'une pièce jointe survit tant qu'une liaison le cite (D24)",
      true]),

    deplacer: (m, dest) => appliquer(m, { dossier: dest || null }, ["Déplacer vers un dossier",
`UPDATE rattachement SET dossier_id = :dossier WHERE message_id = :id AND compte_id = :moi;`,
      "le dossier utilisateur est une colonne du RATTACHEMENT, pas du message : deux comptes " +
      "classent le même message différemment (D51/D36)"]),

    /* Vider la corbeille : le seul endroit où la déduplication se paie. */
    viderCorbeille(liste) {
      const n = liste.length;
      liste.slice().forEach(m => { St.patch(m, { suppr: true }); C.retire(m); });
      C.recompte(); St.save();
      ABX.log("Vider la corbeille — " + n + " message(s)",
`-- on ne supprime PAS le message : on supprime le RATTACHEMENT
DELETE FROM rattachement WHERE compte_id = :moi AND dossier_id = :trash;

-- le message ne part que lorsque plus personne ne le porte (D10)
DELETE FROM message m WHERE NOT EXISTS
  (SELECT 1 FROM rattachement r WHERE r.message_id = m.message_id);

-- et le blob d'une pièce jointe, que lorsque plus aucune liaison ne le cite (D24)
DELETE FROM piece_jointe p WHERE NOT EXISTS
  (SELECT 1 FROM message_piece_jointe l WHERE l.pj_id = p.pj_id);`,
        "⚠ la déduplication impose un RAMASSE-MIETTES : rien ne s'efface en cascade depuis un " +
        "compte. À faire en tâche de fond, jamais dans le clic — sinon vider la corbeille " +
        "balaye message et piece_jointe entières", true);
      ABX.Bus.emit("corpus:changed", {});
    },
  };

  ABX.MessageService = M;
})(window.ABX = window.ABX || {});
