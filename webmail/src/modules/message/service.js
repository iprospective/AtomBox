/* SERVICE MÉTIER — les gestes sur un message.

   Chaque action fait trois choses, toujours dans cet ordre : elle mute l'état,
   elle journalise la requête qu'elle aurait écrite en base, elle émet. Aucune
   vue n'est appelée d'ici : c'est le contrôleur qui décide quoi repeindre. */
(function (ABX) {
  "use strict";
  const St = ABX.Store, C = ABX.Corpus;

  /* Un geste sur un message = UN appel à la couche d'accès (D141) : PATCH du
     rattachement, ou DELETE (détacher, D118). L'état local est mis à jour tout
     de suite (l'interface répond) ; la promesse confirme, et les compteurs se
     rechargent. En prod c'est la latence réseau ; en POC c'est immédiat — mais
     l'interface est déjà écrite pour l'attente. */
  /* LES DATES SUIVENT LA TRANSITION (D175) : c'est le serveur qui les pose, dans la case de l'état
     où elle a eu lieu. On les REFLÈTE ici pour que l'écran réponde tout de suite, sans les
     ENVOYER — envoyer un `sorti_le` nu, c'était pouvoir dater un traitement sans dire qu'il avait
     eu lieu. Et l'on ne touche PAS les dates au retour dans la file : elles sont des faits. */
  const DATE_DE = { processed:"traite_le", archived:"archive_le", deleted:"supprime_le", junk:"junk_le" };
  function refleterSortie(m, valeur) {
    const champ = DATE_DE[valeur];
    if (!champ) { m.sorti_le = null; return; }
    m[champ] = m[champ] || Date.now();
    m.sorti_le = m[champ];
  }

  function appliquer(m, patch, log) {
    Object.assign(m, patch);                       // optimiste : l'écran répond
    if ("motif_sortie" in patch) refleterSortie(m, patch.motif_sortie);
    const p = patch.suppr ? ABX.Api.detacher(m.id) : ABX.Api.patcher(m.id, patch);
    if (typeof log === "function") log(m);
    else if (log) ABX.log(...(Array.isArray(log) ? log : [log]));
    return p.then(r => ABX.Api.compteurs().then(() => {   // les non-lus / la file bougent
      ABX.Bus.emit("corpus:changed", { message: m, patch, reponse: r });   // …puis on repeint
      return r;
    }));
  }

  /* la trace pédagogique seule — `appliquer` écrivait ET traçait ; poser un tag écrit ailleurs
     (sa propre route), mais doit tracer pareil. */
  function tracer(m, log) {
    if (typeof log === "function") log(m);
    else if (log) ABX.log(...(Array.isArray(log) ? log : [log]));
  }

  const M = {
    appliquer,

    /* `muet` : l'ouverture d'un message décrit déjà cette écriture dans sa
       cascade — inutile de la journaliser deux fois. */
    lire: (m, muet) => appliquer(m, { lu: true }, muet ? null : ["Marquer lu",
`INSERT INTO read_state (compte_id, comm_id, boite_id, opened_at, last_seen_at, open_count, flagged)
VALUES (:moi, :id, :boite, now(), now(), 1, false)
ON CONFLICT ON CONSTRAINT pk_read_state DO UPDATE
   SET opened_at = COALESCE(read_state.opened_at, excluded.opened_at),
       last_seen_at = now(), open_count = read_state.open_count + 1;`,
      "une ÉCRITURE à chaque ouverture — le prix d'un compteur de non-lus juste. Elle va sur la " +
      "PERSONNE, pas sur le rattachement (D175) : sur une boîte partagée, « lu » sans dire par qui " +
      "ne veut rien dire. Le COALESCE garde la PREMIÈRE ouverture : un fait, qui ne se réécrit pas"]),

    /* LE DRAPEAU (RM3244, D140c) — un concept IMAP (\\Flagged), que la transition oblige à montrer :
       posé sur le téléphone, il doit se voir ici ; posé ici, il doit se voir sur le téléphone. Le
       suivi propre à AtomBox reste le STATUT et la file de travail (D093, D013). */
    drapeau: m => appliquer(m, { drapeau: !m.drapeau }, [m.drapeau ? "Retirer le drapeau" : "Poser un drapeau",
`INSERT INTO read_state (compte_id, comm_id, boite_id, open_count, flagged)
VALUES (:moi, :id, :boite, 0, :valeur)
ON CONFLICT ON CONSTRAINT pk_read_state DO UPDATE SET flagged = :valeur;
-- puis l'ordre montant : rattachement.change → STORE ±FLAGS (\\Flagged) sur l'UID source (F113)`,
      "le drapeau est PERSONNEL (D175) : chacun s'authentifie en IMAP avec son compte, donc \\Flagged " +
      "ne peut dire que « MOI je l'ai marqué ». open_count reste à 0 : poser un drapeau n'est pas lire"]),

    /* « À REVOIR » A REMPLACÉ « MARQUER NON LU » (D175 § 2). Le geste ne change pas — même bouton,
       même raccourci, même gras dans la liste. Le mot change, et il devient vrai : *j'y suis passé,
       il faut que j'y retourne*. « Non lu » ne voulait plus rien dire une fois qu'on garde la date
       d'ouverture — et l'ancien geste EFFAÇAIT cette date, c'est-à-dire la seule trace que
       quelqu'un avait regardé le message. */
    nonLu: m => appliquer(m, { a_revoir: !m.a_revoir }, [m.a_revoir ? "Ne plus revoir" : "À revoir",
`INSERT INTO marker_personal (compte_id, comm_id, boite_id, marker_id, set_at)
SELECT :moi, :id, :boite, marker_id, now() FROM marker WHERE code = 'to_review'
ON CONFLICT ON CONSTRAINT pk_marker_personal DO NOTHING;`,
      "une table CREUSE : une ligne seulement quand le marqueur est posé, un message sur cent. Et " +
      "opened_at n'est pas touché — on n'efface pas un FAIT pour exprimer une INTENTION (D175)"]),

    traiter: m => appliquer(m, { motif_sortie:"processed" },
      x => ABX.Traces.muter(x, {
        label:"Marquer traité", nom:"traiter",
        corps:{ motif_sortie: "processed" },
        retour:{ comm_id: x.id, motif_sortie: "processed",
                 traite_le: "2026-09-01T14:02:11+02:00", sorti_le: "2026-09-01T14:02:11+02:00" },
      }, [
        { t:"sql", label:"l'état courant, et la date de CETTE transition",
          detail:
`UPDATE rattachement SET exit_reason = 'processed',
       processed_at = COALESCE(processed_at, now()), processed_by = :moi
 WHERE comm_id = :id AND boite_id = :boite;`,
          index:"UN état courant (exclusif : un message est dans une seule boîte aux lettres) mais " +
                "QUATRE couples de dates. Un message est généralement traité PUIS archivé des " +
                "années après : si l'archivage écrasait processed_at, on perdrait la clé " +
                "d'archivage (D014) — la donnée qui commande la transition suivante. Le COALESCE " +
                "dit la même chose : une date posée est un fait, elle ne se repose pas" },
        { t:"sql", label:"le chemin parcouru : « traité », daté, signé",
          detail:
`INSERT INTO journal (journal_id, quand, qui, action, cible_type, cible_id, details)
VALUES (:uuid, now(), :moi, 'processed', 'rattachement', :id, :details);`,
          index:"deux écritures pour un clic, et c'est voulu : l'état COURANT d'un côté, le CHEMIN " +
                "de l'autre. « Traité le 3, puis archivé le 10 » ne se lit plus sur la ligne — " +
                "seul le journal le raconte, et il n'est jamais purgé (D054)" },
        { t:"event", label:"les applications connectées sont prévenues",
          detail:
`INSERT INTO evenement_sortant (application_id, type, charge, etat, prochaine_tentative)
SELECT application_id, 'message.traite', :json, 'a_emettre', now()
  FROM abonnement WHERE type = 'message.traite';`,
          index:"un ERP qui suit ses échanges veut savoir qu'un message a été traité — mais " +
                "l'apprendre ne doit pas retarder le clic (D086)" },
      ])),

    archiver: m => appliquer(m, { motif_sortie:"archived" }, ["Archiver",
`UPDATE rattachement SET exit_reason = 'archived',
       archived_at = COALESCE(archived_at, now()), archived_by = :moi
 WHERE comm_id = :id AND boite_id = :boite;`,
      "processed_at SURVIT : un message est généralement traité puis archivé des années après " +
      "(D175 § 4 bis), et y arriver sans traitement reste possible (D030). Les cinq boîtes aux " +
      "lettres — INBOX, Traités, Archivés, Corbeille, Indésirables — sont les valeurs de cette " +
      "seule colonne, lues : c'est D051 réalisée"]),

    /* Remettre dans la file : l'ÉTAT s'efface, ET le statut cesse d'être « traité » — un message
       qui revient dans la file en portant « traité » est un message qu'on ne retraitera jamais.
       Les DATES, elles, restent : « il a été traité le 3 » est vrai même s'il est revenu. */
    refile: m => appliquer(m, { motif_sortie:null, sorti_le:null,
                                ...(m.statut === "processed" ? { statut: "todo" } : {}) }, ["Remettre dans la file",
`UPDATE rattachement SET exit_reason = NULL WHERE comm_id = :id AND boite_id = :boite;`,
      "⚠ retour de partition : c'est exactement Q009 (« un email sorti peut-il revenir ? »). " +
      "Autorisé ici — reste à décider si le cas est courant ou exceptionnel, la réponse " +
      "change le partitionnement. Noter ce qu'on n'efface PAS : processed_at reste, c'est un fait", true]),

    corbeille: m => appliquer(m, { dossier:"trash" },
      x => ABX.Traces.muter(x, {
        label:"Mettre à la corbeille", nom:"corbeille",
        corps:{ dossier: "trash" },
        retour:{ comm_id: x.id, dossier_id: "trash",
                 dossier_origine: (x.dossier_origine || "inbox"), deplace_le: "2026-09-01T14:02:11+02:00" },
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
      const st = (ABX.Ref.statuts || []).find(s => s.id === id) || { id, label: id };
      st.sortie = st.sortie || (id === "processed" ? "processed" : null);   // « traité » sort de la file (D093, D014)
      const patch = { statut: id };
      if (st.sortie) patch.motif_sortie = st.sortie;
      else if (m.motif_sortie === "processed") patch.motif_sortie = null;
      appliquer(m, patch, x => ABX.Traces.muter(x, {
        label:"Statut : " + st.label, nom:"statuer",
        corps:{ statut: id },
        retour:{ comm_id: x.id, statut: id,
                 statut_le: "2026-09-01T14:02:11+02:00",
                 motif_sortie: st.sortie || null },
      }, [
        { t:"sql", label:"une colonne, pas une ligne de plus — et la transition est SIGNÉE",
          detail:
`UPDATE rattachement SET status = :statut, status_at = now(), status_by = :moi` + (st.sortie
  ? `,\n       exit_reason = 'processed', processed_at = COALESCE(processed_at, now()), processed_by = :moi`
  : `,\n       exit_reason = NULL`) + `
 WHERE comm_id = :id AND boite_id = :boite;`,
          index: st.sortie
            ? "⚠ « traité » est le seul statut qui SORT de la file : il écrit exit_reason, donc " +
              "déplace la partition (D014/D030). Les autres se contentent de bouger dans la file"
            : "status est un ENUM ordonné sur le rattachement : fermé, donc indexable, et " +
              "COLLECTIF — un par boîte, pas par personne (D175 § 5 tranche Q035). Ce qui est " +
              "personnel, c'est la lecture et les marqueurs, pas le workflow",
          warn: !!st.sortie },
        { t:"sql", label:"le changement d'état s'écrit au journal, avec l'avant et l'après",
          detail:
`INSERT INTO journal (journal_id, quand, qui, action, cible_type, cible_id, details)
VALUES (:uuid, now(), :moi, 'status_changed', 'rattachement', :id,
        jsonb_build_object('avant', :avant, 'apres', :statut));`,
          index:"c'est ce qui permettra de mesurer un délai de traitement — la seule métrique " +
                "que personne ne pense à stocker avant d'en avoir besoin. Et l'avant/après en fait " +
                "un CHEMIN plutôt qu'une liste d'événements" },
        { t:"note", label:"pourquoi pas un tag « à faire » ?",
          detail:"parce qu'un tag classe et qu'un statut pilote",
          index:"un tag est ouvert, interopérable et soumis à l'ACL d'un axe (D017/D018) : une " +
                "application connectée pourrait vider votre file de travail. Un statut est " +
                "fermé, ordonné, propre au compte — deux mécaniques, deux tables" },
      ]));
    },

    /* RECHARGER LE RÉFÉRENTIEL AVANT DE REPEINDRE (F139, D169).

       Poser `projet = dolibarr` créait la valeur côté serveur et ne la montrait NULLE PART :
       l'arborescence lit `Ref.valeurs`, chargé une fois au démarrage, et le client repeignait le
       référentiel d'il y a dix minutes. Il fallait recharger la page pour voir la branche.

       Ce n'est pas un manque de temps réel — c'est l'onglet de celui qui vient d'agir qui était
       faux. On ne recharge QUE pour les actions qui peuvent créer une entrée de référentiel : un
       « lu » ne doit pas payer deux requêtes de plus. Les compteurs suivent, sans quoi la branche
       neuve s'afficherait à zéro. */
    rafraichirReferentiel(m) {
      return Promise.resolve(ABX.Ref.charger())
        .then(() => ABX.Api.compteurs())
        .catch(() => null)                    // un référentiel non rechargé ne doit pas perdre le tag posé
        .then(() => { ABX.Bus.emit("corpus:changed", m ? { message: m } : {}); });
    },

    /* Les tags sont posés sur le MESSAGE, pas sur le rattachement (D017) : c'est ce
       qui les rend interopérables entre applications. Un tag posé par un connecteur
       et retiré à la main sera reposé au passage suivant — l'écran doit le dire. */
    ajouterTag(m, axe, val) {
      if (!axe || !val.trim()) return;
      const v = val.trim();
      if (m.tags.some(t => t.axe === axe && t.val === v)) return;
      /* Le tag est sur le MESSAGE, pas sur le rattachement (D017) : il a sa route à lui.
         Il passait par le PATCH du rattachement, que le serveur ignorait — le tag s'affichait,
         et disparaissait au rechargement. */
      m.tags = m.tags.concat([{ axe, val: v, source: "manuel" }]);            // optimiste
      const envoi = ABX.Api.poserTag(m.id, axe, v)
        .then(r => { if (r && r.tags) m.tags = r.tags; return M.rafraichirReferentiel(m).then(() => r); });
      tracer(m,
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
      return envoi;
    },

    retirerTag(m, i) {
      const t = m.tags[i];
      if (!t) return;
      const auto = t.source && t.source !== "manuel";
      m.tags = m.tags.filter((_, k) => k !== i);                             // optimiste
      const envoi = ABX.Api.retirerTag(m.id, t.axe, t.val)
        .then(r => { if (r && r.tags) m.tags = r.tags; return M.rafraichirReferentiel(m).then(() => r); });
      tracer(m,
        ["Retirer le tag " + t.axe + " = " + t.val,
`DELETE FROM comm_tag
 WHERE comm_id = :id AND tag_id = :tag AND pose_par = :moi;

-- le tag lui-même n'est PAS supprimé : d'autres messages le portent`,
          auto
            ? "⚠ ce tag a été posé par « " + t.source + " » : le retirer ici ne l'empêche pas " +
              "d'être reposé au prochain passage du connecteur. Un retrait durable suppose " +
              "soit une table d'exclusions, soit un retrait côté application (D019/D021)"
            : "le tag reste en base tant qu'un autre message le porte — supprimer la ligne de " +
              "liaison n'est pas supprimer le tag",
          auto]);
      return envoi;
    },

    /* Vider la corbeille : le seul endroit où la déduplication se paie. */
    viderCorbeille(liste) {
      const n = liste.length;
      liste.slice().forEach(m => { Object.assign(m, { suppr: true }); ABX.Api.detacher(m.id); });
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
