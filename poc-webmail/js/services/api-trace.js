/* LA SURFACE D'API, DÉCRITE PAR LES GESTES QUI L'APPELLENT.

   Ce fichier est le support de CDC : chaque fonction décrit la **cascade
   complète** d'un geste — clic, appel, route, contrôleur, service, portée,
   requêtes, magasin d'octets, JSON, rendu. Écrire le serveur, ce sera écrire
   ce qui est décrit ici.

   HYPOTHÈSE DE TRAVAIL : une API REST, une ressource par concept du modèle.
   Q007 n'est pas tranchée — un point d'entrée unique (GraphQL, RPC) donnerait
   une autre cascade, avec moins d'allers-retours et plus de complexité côté
   serveur. La trace est faite pour rendre cette comparaison possible, pas pour
   la préempter : lire une cascade et compter ses passages de réseau est le
   moyen le plus direct de trancher Q007. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, Fx = ABX.Fixtures, Erp = ABX.Erp;

  const iso = t => new Date(t).toISOString().slice(0, 19) + "Z";
  const j = o => JSON.stringify(o, null, 2);

  /* La représentation d'un message en JSON — le contrat d'API, rendu tangible.
     Tout ce qui est ici devra exister dans le schéma ; tout ce qui manque ici
     est une colonne dont personne n'a encore eu besoin. */
  function messageJson(m, complet) {
    const o = {
      comm_id: m.id,
      sujet: m.subject,
      de: { nom: m.from, adresse: m.mail },
      a: m.to,
      boite: m.boite,
      sens: m.sens === "out" ? "envoye" : "recu",
      date_reception: iso(m.date),
      lu_le: m.lu ? iso(Date.now()) : null,
      sorti_le: m.sorti ? iso(m.sorti) : null,
      motif_sortie: m.motif,
      thread_id: m.thread,
      taille_octets: m.size * 1024,
      nb_pieces_jointes: m.pj,
    };
    if (!complet) { o.snippet = m.snippet; return o; }
    o.tags = m.tags.map(t => {
      const f = Erp.APPS[t.axe] ? Erp.fiche(t.axe, t.val) : null;
      return { axe: t.axe, valeur: t.val, application: t.src,
               ref_externe: f ? f.ref : null };
    });
    o.pieces_jointes = m.pjs.map((p, i) => ({
      pj_id: p.b.pj_id, ordre: i, nom: p.nom, octets: p.b.ko * 1024,
      mime_declare: p.declare, mime_detecte: p.b.mime,
      sha256: p.b.sha + "…", partage_par: p.b.refs,
    }));
    o.corps = { texte: (m.body || "").slice(0, 60) + "…", html: null };
    return o;
  }

  const Traces = {
    messageJson,

    /* ------------------------------------------------------------------ */
    ouvrirMessage(m, dejaLu) {
      const e = [
        { t:"ui", label:"clic sur la carte du message",
          detail:"views/partials.js « message.card » → Controllers.Tabs.ouvrir({type:'msg', id})" },
        { t:"cache", label:"le message est-il déjà en mémoire ?",
          detail: "Store.ui.tabs — un onglet déjà ouvert ne redemande rien",
          index:"c'est tout l'intérêt d'un onglet : le second affichage coûte zéro requête" },
        { t:"http", label:"une seule requête, corps et pièces jointes compris",
          detail:"GET /api/v1/messages/" + m.id + "?inclure=corps,pieces_jointes,tags,fil\n"
               + "Authorization: Bearer <token de session>\nAccept: application/json",
          index:"le paramètre `inclure` évite le N+1 côté client : sans lui, il faut une " +
                "requête pour le corps, une pour les PJ, une pour le fil — trois allers-retours " +
                "pour ouvrir un message" },
        { t:"route", label:"routes/api.php",
          detail:"GET /api/v1/messages/{id} → MessageController::show" },
        { t:"ctrl", label:"MessageController::show(id, inclure[])",
          detail:"valide `inclure`, délègue, sérialise — aucune requête écrite ici" },
        { t:"acl", label:"la portée EST le chemin d'accès (D036)",
          detail:"MessageService::pourCompte(id, compte)",
          index:"pas de « SELECT le message puis vérifier » : la portée est une jointure sur " +
                "rattachement, donc un message hors portée n'existe simplement pas — 404, pas 403" },
        { t:"sql", label:"le message et ce que ce compte en a fait",
          detail:
`SELECT m.comm_id, m.sujet, m.from_nom, m.from_adresse, m.date_reception,
       m.taille_octets, m.nb_pieces_jointes, m.thread_id, m.blob_ref,
       r.lu_le, r.sorti_le, r.motif_sortie, r.dossier_id, r.sens
  FROM rattachement r
  JOIN comm m USING (comm_id)
 WHERE m.comm_id = :id AND r.compte_id = :moi;`,
          index:"index (comm_id, compte_id) sur rattachement — jamais SELECT * : les headers " +
                "sont TOASTés (D027) et ne servent pas à l'affichage" },
        { t:"sql", label:"les pièces jointes — liaison et blob",
          detail:
`SELECT l.ordre, l.nom_fichier, l.mime_declare, l.transfer_encoding,
       p.pj_id, p.octets, p.mime_detecte, p.sha256,
       (SELECT count(*) FROM comm_piece_jointe x WHERE x.pj_id = p.pj_id) AS partage_par
  FROM comm_piece_jointe l JOIN piece_jointe p USING (pj_id)
 WHERE l.comm_id = :id ORDER BY l.ordre;`,
          index: m.pj ? "index (comm_id, ordre) ; le sous-select de partage coûte un accès par " +
                        "PJ — à ne garder que si l'écran l'affiche vraiment"
                      : "aucune ligne ici : nb_pieces_jointes valait 0, la requête aurait pu être évitée",
          warn: m.pj > 0 },
        { t:"sql", label:"les tags, avec leur application d'origine",
          detail:
`SELECT t.axe_id, t.valeur, t.ref_externe, a.code AS application
  FROM comm_tag mt JOIN tag t USING (tag_id)
  JOIN application a ON a.application_id = t.application_id
 WHERE mt.comm_id = :id
   AND t.axe_id = ANY (:axes_lisibles_par_moi);`,
          index:"l'ACL des axes est un ANY sur une liste calculée à l'authentification (D018) — " +
                "pas une jointure de plus à chaque message" },
        { t:"sql", label:"le fil de discussion",
          detail:
`SELECT comm_id, from_nom, sujet, date_reception
  FROM comm WHERE thread_id = :thread
 ORDER BY date_reception LIMIT 50;`,
          index:"index (thread_id, date_reception) — D055. ⚠ le fil ignore la portée : un message " +
                "du fil que ce compte ne peut pas voir doit apparaître en creux, pas disparaître (Q026)",
          warn:true },
        { t:"blob", label:"le corps, hors base",
          detail:"zstd -d " + (m.pjs[0] ? "blob/" + m.pjs[0].b.sha.slice(0, 2) + "/" + m.pjs[0].b.sha : "blob/…"),
          index:"les octets ne transitent jamais par PostgreSQL (D005/D007) : la base dit où, " +
                "le magasin donne quoi" },
        { t:"json", label:"200 OK — le contrat d'API",
          detail: j(messageJson(m, true)) },
        { t:"render", label:"Views.Message + partielles du registre",
          detail:"message.tags · erp.panel · attachment.list · thread.item",
          index:"la variante « " + (ABX.Views.List.variante(m) || "aucune") + " » a été choisie " +
                "avant le rendu, d'après le sens et le dossier" },
      ];
      const tg = Erp.tagDe(m);
      if (tg) { const f = Erp.fiche(tg.axe, tg.val);
        e.push(
          { t:"http", label:"un SECOND aller-retour — et il ne va pas chez nous",
            detail:"GET https://" + f.cfg.app + ".lan/api/index.php/thirdparties/" + f.ref + "\n"
                 + "DOLAPIKEY: <clé de l'intégration>",
            index:"le contexte métier n'est pas stocké (D019) : l'afficher coûte un appel à une " +
                  "application qui peut être lente, absente ou tarifée. C'est Q031 — et la raison " +
                  "pour laquelle ce cadre doit se remplir APRÈS le message, jamais avant",
            warn:true },
          { t:"json", label:"200 OK — ce que l'ERP répond",
            detail: j({ id: f.ref, name: tg.val, client: 1,
                        outstanding_total: f.encours, outstanding_late: f.echu,
                        last_documents: f.objets.slice(0, 2).map(o =>
                          ({ type: o.type.toLowerCase(), ref: o.ref,
                             total_ttc: o.montant, statut: o.statut })) }),
            index:"aucun de ces champs n'entre en base AtomBox : le cadre est peint puis oublié. " +
                  "Le jour où on le met en cache, c'est Q031 qui bascule" }); }
      if (!dejaLu) e.push(
        { t:"http", label:"effet de bord : le message devient lu",
          detail:"PATCH /api/v1/messages/" + m.id + "/rattachement\n{ \"lu\": true }",
          index:"un PATCH séparé, et non un effet caché du GET : une lecture ne doit pas écrire, " +
                "sinon un préchargement marque tout comme lu" },
        { t:"sql", label:"une écriture par ouverture",
          detail:
`UPDATE rattachement SET lu_le = now()
 WHERE comm_id = :id AND compte_id = :moi AND lu_le IS NULL;`,
          index:"le IS NULL évite de réécrire une ligne déjà lue — sans lui, chaque relecture " +
                "salit une page (D041)" },
        { t:"render", label:"compteurs de l'arborescence rafraîchis",
          detail:"Corpus.recompte() → Views.Nav",
          index:"côté serveur, ce serait un recalcul incrémental et non une nouvelle requête " +
                "groupée : décrémenter le compteur du dossier, pas le recompter (D078)" });
      ABX.log({ label:"Ouvrir « " + m.subject + " »", etapes:e });
    },

    /* ------------------------------------------------------------------ */
    ouvrirDossier(folder, n) {
      const virtuel = folder.kind === "axe" || folder.kind === "virtuel";
      ABX.log({ label:"Ouvrir le dossier « " + folder.label + " »", etapes:[
        { t:"ui", label:"clic dans l'arborescence",
          detail:"views/nav.js → Controllers.List.ouvrir(folder)" },
        { t:"http", label:"la liste, paginée par curseur",
          detail:"GET /api/v1/messages?dossier=" + folder.id +
                 "&filtre=file&sens=tous&tri=date&limite=50",
          index:"pas de numéro de page : un OFFSET profond coûte de plus en plus cher, et une " +
                "liste de webmail se parcourt sans fin" },
        { t:"route", label:"routes/api.php",
          detail:"GET /api/v1/messages → MessageController::index" },
        { t:"ctrl", label:"MessageController::index(filtres)",
          detail:"traduit les filtres d'écran en critères — le SQL n'est pas construit ici" },
        { t:"svc", label:"ListeService::pour(compte, dossier, filtres)",
          detail:"un seul endroit où se décide la clause WHERE, pour un seul plan d'exécution" },
        { t:"sql", label: virtuel ? "dossier virtuel : le prédicat est un tag" : "dossier réel",
          detail: virtuel
            ? `SELECT m.comm_id, m.sujet, m.from_nom, m.snippet, m.date_reception,
       m.nb_pieces_jointes, r.lu_le, r.sens
  FROM comm_tag mt
  JOIN tag t ON t.tag_id = mt.tag_id
  JOIN rattachement r ON r.comm_id = mt.comm_id AND r.compte_id = :moi
  JOIN comm m ON m.comm_id = mt.comm_id
 WHERE t.axe_id = :axe AND t.valeur = :valeur AND r.sorti_le IS NULL
 ORDER BY m.date_reception DESC LIMIT 50;`
            : `SELECT m.comm_id, m.sujet, m.from_nom, m.snippet, m.date_reception,
       m.nb_pieces_jointes, r.lu_le, r.sens
  FROM rattachement r JOIN comm m USING (comm_id)
 WHERE r.compte_id = :moi AND r.dossier_id = :dossier AND r.sorti_le IS NULL
 ORDER BY m.date_reception DESC LIMIT 50;`,
          index: virtuel
            ? "index (tag_id, date_reception DESC) avec la date DÉNORMALISÉE dans la liaison — " +
              "sinon PostgreSQL trie après avoir tout lu (D016)"
            : "index partiel (compte_id, dossier_id, date_reception DESC) WHERE sorti_le IS NULL — " +
              "sa taille est celle de la file, pas celle du corpus" },
        { t:"json", label:"200 OK — " + n + " message(s), forme abrégée",
          detail: j({ curseur_suivant: "eyJkIjoiMjAyNi0wNy0yOSIsImkiOjkxfQ",
                      total_estime: n,
                      messages: ["… " + n + " objets abrégés : id, sujet, de, date, lu_le, sens, " +
                                 "nb_pieces_jointes, snippet …"] }),
          index:"« total_estime » et non « total » : compter exactement les messages d'un dossier " +
                "de 200 000 lignes coûte plus cher que d'en afficher 50" },
        { t:"render", label:"Views.List → une carte par message",
          detail:"le registre choisit la variante de chaque carte (dossier, puis sens, puis axe)" },
      ]});
    },

    /* ------------------------------------------------------------------ */
    /* Une capacité enfichable : la MÊME intention, deux cascades très
       différentes selon le fournisseur branché. C'est ce contraste qui doit
       décider — pas une préférence de principe. */
    capacite(cap, geste, m, natifEtapes, distantEtapes) {
      const P = ABX.Providers, f = P.actif(cap);
      const e = [
        { t:"ui", label:"clic sur « " + geste + " »",
          detail:"views/message.js → Capacites." + cap + "(message)" },
        { t:"svc", label:"le contrat, pas l'implémentation",
          detail:"Capacites.resoudre('" + cap + "') → « " + f.label + " »",
          index:"l'écran ne sait pas lequel est branché ; il appelle " +
                P.CAPACITES[cap].contrat[0] + " et c'est tout" },
      ];
      ABX.log({ label: geste + " — via " + f.label,
        etapes: e.concat(f.id === "natif" ? natifEtapes(f) : distantEtapes(f)).concat([
          { t:"render", label:"le même écran, quel que soit le fournisseur",
            detail:"aucune vue conditionnelle",
            index: f.note },
        ]) });
    },

    /* ------------------------------------------------------------------ */
    /* L'envoi : le seul geste qui écrit un message plutôt qu'un rattachement,
       et le seul qui sorte d'AtomBox. */
    envoyer(m, d, internes, externes) {
      const e = [
        { t:"ui", label:"clic sur « Envoyer »",
          detail:"views/compose.js → Controllers.Compose.finir(onglet, true)" },
        { t:"http", label:"le message est une ressource, pas une action",
          detail:"POST /api/v1/messages\n" + j({
            de: d.de, a: m.to,
            cc: d.cc.split(",").map(x => x.trim()).filter(Boolean),
            sujet: m.subject, corps: { texte: "…" },
            pieces_jointes: m.pjs.map(p => ({ pj_id: p.b.pj_id, nom: p.nom })),
            reference: d.ref && d.src ? d.src : null }),
          index:"les pièces jointes sont référencées par leur pj_id, pas transmises : elles ont " +
                "été téléversées AVANT, ce qui rend l'envoi idempotent et réessayable" },
        { t:"route", label:"routes/api.php",
          detail:"POST /api/v1/messages → MessageController::store" },
        { t:"svc", label:"EnvoiService::envoyer(compte, brouillon)",
          detail:"partage les destinataires : " + internes.length + " interne(s), " +
                 externes.length + " externe(s)",
          index:"ce partage est le cœur de D012, et il se fait ICI — pas dans Postfix, qui n'a " +
                "aucun moyen de savoir ce qui a déjà été livré en base" },
        { t:"sql", label:"BEGIN — le message est écrit UNE fois (D010)",
          detail:
`INSERT INTO comm (comm_id, sujet, corps, from_adresse, date_envoi, blob_ref)
VALUES (:id, :sujet, :corps, '` + d.de + `', now(), :ref);`,
          index:"le corps part au magasin d'octets, pas dans la colonne : la base indexe, elle " +
                "ne stocke pas (D005/D007)" },
        { t:"sql", label:"l'expéditeur — sorti de la file dès l'écriture",
          detail:
`INSERT INTO rattachement (comm_id, compte_id, boite_id, sens,
                          recu_le, sorti_le, motif_sortie)
VALUES (:id, :moi, :boite, 'envoye', now(), now(), 'envoye');`,
          index:"le sens est posé ICI, à l'émission (D090) : c'est ce qui rend le filtre " +
                "« reçus / envoyés » indexable au lieu d'être déduit de from_adresse" },
      ];
      if (internes.length) e.push(
        { t:"sql", label:internes.length + " destinataire(s) interne(s) — livrés en base, sans SMTP",
          detail:
`INSERT INTO rattachement (comm_id, compte_id, boite_id, sens, recu_le)
SELECT :id, b.compte_id, b.boite_id, 'recu', now() FROM boite b
 WHERE b.adresse = ANY (:internes);   -- ` + internes.join(", "),
          index:"une ligne par destinataire, un seul message : c'est exactement ce que la " +
                "déduplication devait donner (D010/D012)" });
      if (d.ref && d.src) e.push(
        { t:"sql", label:"transfert par référence : un lien et une ACL, aucune copie",
          detail:
`INSERT INTO message_lien (message_porteur, message_source, type)
VALUES (:id, '` + d.src + `', 'reference');
INSERT INTO acl_message (comm_id, principal, droit, accorde_par)
SELECT '` + d.src + `', a, 'lire', :moi FROM unnest(:internes) a;`,
          index:"l'ACL est indépendante et durable (D060) : le destinataire garde l'accès même si " +
                "l'expéditeur perd le sien (D058/D067)" });
      e.push({ t:"sql", label:"COMMIT", detail:"COMMIT;",
        index:"tout ce qui précède est atomique ; tout ce qui suit ne l'est pas, et ne doit " +
              "surtout pas l'être" });
      if (externes.length) e.push(
        { t:"event", label:externes.length + " destinataire(s) externe(s) — après le COMMIT",
          detail:"SELECT pg_notify('smtp_out', :id);   -- " + externes.join(", "),
          index: internes.length
            ? "⚠ destinataires MIXTES : le relais ne doit remettre QUE les externes, sinon les " +
              "internes reçoivent deux fois. C'est le point soulevé pour D012, et il se règle " +
              "dans cette liste, pas dans la configuration de Postfix"
            : "remise au relais après COMMIT : un SMTP lent ne doit jamais tenir une transaction " +
              "ouverte",
          warn: internes.length > 0 });
      e.push(
        { t:"json", label:"201 Created — le message tel qu'il est en base",
          detail: j(messageJson(m, false)),
          index:"le client n'a pas à reconstruire ce qu'il vient d'envoyer : il l'affiche tel " +
                "que le serveur l'a enregistré, identifiant compris" },
        { t:"render", label:"l'onglet de composition se ferme, celui du message s'ouvre",
          detail:"Controllers.Tabs.fermer(compo) → Controllers.Tabs.ouvrir(message)" });
      ABX.log({ label:"Envoyer « " + m.subject + " »", etapes:e });
    },

    /* ------------------------------------------------------------------ */
    /* Une mutation : le clic, le PATCH, le contrôleur, la portée, les écritures
       (fournies par l'appelant), la réponse, le rafraîchissement. */
    muter(m, action, etapesSql) {
      ABX.log({ label: action.label, etapes: [
        { t:"ui", label:"clic sur l'action",
          detail:"views/message.js → MessageService." + action.nom + "(message)" },
        { t:"http", label:"une mutation, une ressource",
          detail:"PATCH /api/v1/messages/" + m.id + "/rattachement\n" + j(action.corps),
          index:"c'est le RATTACHEMENT qu'on modifie, pas le message : l'URL le dit, et c'est " +
                "ce qui empêche un client d'écrire sur un fait partagé (D036)" },
        { t:"route", label:"routes/api.php",
          detail:"PATCH /api/v1/messages/{id}/rattachement → RattachementController::update" },
        { t:"acl", label:"la portée est dans l'écriture elle-même",
          detail:"… WHERE comm_id = :id AND compte_id = :moi",
          index:"aucune vérification préalable : un compte hors portée met à jour zéro ligne, " +
                "et le contrôleur répond 404 sur ce zéro" },
      ].concat(etapesSql).concat([
        { t:"json", label:"200 OK — le nouvel état, pas un accusé vide",
          detail: j(action.retour),
          index:"renvoyer l'état évite au client de deviner ce que le serveur a fait, et de " +
                "diverger silencieusement au premier conflit" },
        { t:"render", label:"liste, arborescence et onglet rafraîchis",
          detail:"Bus « corpus:changed » → Controllers.App.peindre('all')" },
      ]) });
    },
  };

  ABX.Traces = Traces;
})(window.ABX = window.ABX || {});
