/* CONTRÔLEUR MESSAGE — actions, pièces jointes, intégration ERP. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom, St = ABX.Store, C = ABX.Corpus, M = ABX.MessageService;
  const F = ABX.Fmt, At = ABX.Attachments, Erp = ABX.Erp;
  const App = () => ABX.Controllers.App;

  const Message = {
    peindre(t) {
      const m = C.par(t.id);
      if (!m) return void D.paint("detail", `<div class="empty">Ce message n'existe plus.</div>`);
      const el = D.paint("detail", ABX.Views.Message.render(m, St.ui));
      App().bindRetour(el);

      const suivre = el.querySelector("#suivre");
      if (suivre) suivre.onclick = () => ABX.Controllers.Tabs.ouvrir({ type:"msg", id:m.ref }, false);

      const stat = el.querySelector("#stat");
      if (stat) stat.onchange = e => M.statuer(m, e.target.value);

      /* Le menu « ⋯ » : ouvert au clic, fermé au clic suivant ou sur Échap. */
      const menu = el.querySelector("#menu"), plus = el.querySelector("#plus");
      if (plus) {
        plus.onclick = e => { e.stopPropagation(); menu.hidden = !menu.hidden; };
        el.onclick = e => { if (!menu.hidden && !e.target.closest("#menu")
                            && !e.target.closest("#plus")) menu.hidden = true; };
        D.on(el, "[data-move]", "onclick", b => { menu.hidden = true;
                                                  M.deplacer(m, b.dataset.move); });
        D.on(el, "[data-m]", "onclick", b => { menu.hidden = true; Message.menu(m, b.dataset.m); });
      }

      D.on(el, "[data-x]", "onclick", b => M[b.dataset.x](m));
      D.on(el, "[data-untag]", "onclick", b => M.retirerTag(m, +b.dataset.untag));
      Message.cablerTags(el, m);
      D.on(el, "[data-c]", "onclick", b => ABX.Controllers.Compose.demarrer(b.dataset.c, m));
      D.on(el, "[data-a]", "onclick", b => Message.logMessage(b.dataset.a, m));
      D.on(el, ".pjc",     "onclick", c => Message.logPieceJointe(m, +c.dataset.pj));
      D.on(el, "[data-e]", "onclick", b => Message.logErp(m, b.dataset.e));
    },

    /* Le champ de valeur propose les valeurs existantes de l'axe choisi : sans
       cela, chacun écrit « Belair SAS », « belair » et « Belair sas », et l'axe
       ne regroupe plus rien — c'est la gouvernance des axes de Q05, vue de l'écran. */
    cablerTags(el, m) {
      const axe = el.querySelector("#t_axe"), val = el.querySelector("#t_val");
      const liste = el.querySelector("#t_vals");
      if (!axe || !val) return;
      const proposer = () => {
        const vals = (ABX.Fixtures.valeurs[axe.value] || []).slice(0, 200);
        liste.innerHTML = vals.map(v => `<option value="${F.esc(v.label)}">`).join("");
      };
      axe.onchange = proposer;
      proposer();
      const ajouter = () => M.ajouterTag(m, axe.value, val.value);
      el.querySelector("#t_add").onclick = ajouter;
      val.onkeydown = e => { if (e.key === "Enter") ajouter(); };
    },

    /* Les entrées du menu : trois vont au message, trois aux capacités. */
    menu(m, quoi) {
      if (quoi === "archiver") return M.archiver(m);
      if (quoi === "tache")    return ABX.Capacites.creerTache(m);
      if (quoi === "contact")  return ABX.Capacites.ficheContact(m);
      if (quoi === "fichiers") return m.pjs.forEach((_, i) => ABX.Capacites.deposerFichier(m, i));
      return Message.logMessage(quoi, m);
    },

    logMessage(quoi, m) {
      const A = {
        orig: ["Télécharger le message original (.eml)",
`-- réassemblage : le corps, puis chaque partie ré-encodée À L'IDENTIQUE (D25)
-- blob_ref et headers vivent dans la FILLE, pas dans le tronc (D138)
SELECT blob_ref, headers FROM comm_email WHERE comm_id = :id;
SELECT l.ordre, l.nom_fichier, l.mime_declare, l.transfer_encoding, l.disposition,
       l.parametres, p.blob_ref
  FROM comm_piece_jointe l JOIN piece_jointe p USING (pj_id)
 WHERE l.comm_id = :id ORDER BY l.ordre;`,
          "la liaison doit conserver l'ordre, l'encodage et les paramètres de partie : sans eux le " +
          "message se reconstruit mais DKIM ne se revérifie plus (D25/D26)"],
      }[quoi];
      ABX.log(A[0], A[1], A[2], A[3]);
    },

    logPieceJointe(m, i) {
      const p = m.pjs[i], b = p.b;
      ABX.log("Ouvrir « " + p.nom + " »",
`SELECT p.blob_ref, p.sha256, p.mime_detecte, p.octets,
       l.nom_fichier, l.mime_declare, l.transfer_encoding, l.ordre
  FROM comm_piece_jointe l JOIN piece_jointe p USING (pj_id)
 WHERE l.comm_id = :id AND l.pj_id = ${b.pj_id};
-- les octets ne transitent jamais par PostgreSQL : zstd -d <blob_ref> (D05/D07)`,
        "index (comm_id, ordre) sur la liaison — le fichier lui-même reste hors base");

      ABX.log("« " + p.nom + " » — qui d'autre porte CES octets ?",
`SELECT m.comm_id, m.sujet, l.nom_fichier, m.date_reception
  FROM comm_piece_jointe l JOIN comm m USING (comm_id)
 WHERE l.pj_id = ${b.pj_id}      -- ${b.refs} liaison(s) pour un seul blob de ${F.poids(b.ko)}
 ORDER BY m.date_reception DESC LIMIT 50;`,
        b.refs > 1
          ? "index (pj_id, comm_id) — sans ce sens de parcours, la dédup n'est qu'un gain de " +
            "disque : ici elle économise " + F.poids(b.ko * (b.refs - 1)) +
            " et donne « où ai-je déjà vu ce fichier ? » (D24)"
          : "index (pj_id, comm_id) — un seul porteur ici : sur ce fichier la dédup ne gagne " +
            "rien, et c'est le cas le plus fréquent. Le gain vient des quelques blobs très partagés");

      if (At.recompressable(b)) ABX.log("Recompression proposée (D70)",
`-- geste EXPLICITE, jamais automatique
UPDATE piece_jointe
   SET blob_origine = blob_ref, blob_ref = :neuf, octets = :neufs, recompresse_le = now()
 WHERE pj_id = ${b.pj_id};`,
        "⚠ le blob est partagé par " + b.refs + " liaison(s) : un seul UPDATE libère ≈ " +
        F.poids(At.gain(b)) + " mais modifie l'octet de TOUS les porteurs — l'original doit rester " +
        "tant qu'un message doit être revérifiable (D25/D26)", true);
    },

    logErp(m, quoi) {
      const tg = Erp.tagDe(m); if (!tg) return;
      const f = Erp.fiche(tg.axe, tg.val), c = f.cfg, o = ABX.PRNG.pick(f.objets);
      const E = {
        res: {
          label: "Comment ce message a été rattaché à « " + tg.val + " »",
          index: "trois étages, et aucun n'est facultatif : sans le second, AtomBox connaît " +
                 "l'identité mais pas le tiers ; sans le troisième, personne ne pose le tag",
          enfants: [
            { label: "1. l'adresse pointe une IDENTITÉ, jamais l'inverse (D35)",
              sql:
`SELECT c.correspondant_id, c.libelle
  FROM adresse a JOIN correspondant c USING (correspondant_id)
 WHERE a.adresse = lower('${m.mail}');`,
              index: "index UNIQUE (adresse) — un correspondant, N adresses : changer d'adresse " +
                     "ne coupe pas l'historique du tiers" },
            { label: "2. l'identité est reliée au tiers de CHAQUE application connectée",
              sql:
`SELECT application_id, ref_externe FROM correspondant_externe
 WHERE correspondant_id = :cid;               -- ${c.app} → ${f.ref}`,
              index: "index (correspondant_id) — c'est la table D85, sans laquelle le " +
                     "rattachement automatique n'existe pas" },
            { label: "3. le tag est posé par le CONNECTEUR, pas par AtomBox (D21)",
              sql:
`-- aucune requête ici : c'est l'application qui appelle POST /messages/{id}/tags
-- Adresse inconnue ⇒ message sans tag. C'est voulu, pas un échec d'ingestion.` },
          ] },

        lie: {
          label: "Lier ce message à " + o.type.toLowerCase() + " " + o.ref,
          kind: "api",
          sql:
`POST /api/v1/messages/{comm_id}/tags        Authorization: Bearer <token ${c.app}>
{ "axe": "${tg.axe}", "valeur": "${tg.val}",
  "ref_externe": "${f.ref}", "piece": "${o.ref}" }`,
          index: "l'ACL de l'axe est vérifiée avant d'écrire (D18) : poser un tag sur un axe " +
                 "qu'on ne peut que lire doit être refusé, pas ignoré",
          enfants: [
            { label: "le tag de CETTE application, créé ou mis à jour",
              sql:
`INSERT INTO tag (axe_id, application_id, valeur, ref_externe)
VALUES (:axe, :app, :valeur, :ref)
ON CONFLICT (axe_id, application_id, valeur) DO UPDATE
   SET ref_externe = EXCLUDED.ref_externe
RETURNING tag_id;`,
              index: "l'application est DANS la clé d'unicité (D20) : quatre Dolibarr font " +
                     "quatre jeux de tags et aucun n'écrase l'autre (D17)" },
            { label: "la liaison message ↔ tag",
              sql:
`INSERT INTO comm_tag (comm_id, tag_id, pose_par, pose_le)
VALUES (:id, :tag, :application, now()) ON CONFLICT DO NOTHING;`,
              index: "pas d'unicité (message, axe) : un message peut relever de deux clients" },
          ] },

        inv: {
          label: "Onglet « Emails » de la fiche " + f.ref + ", vu depuis " + c.app,
          kind: "api",
          sql:
`GET /api/v1/messages?axe=${tg.axe}&valeur=${encodeURIComponent(tg.val)}
    &application=${c.app}&limite=20&curseur=eyJkIjoiMjAyNi0wMy0xMSIsImkiOjkxfQ
Authorization: Bearer <token opaque de l'application>          -- D63`,
          index: "un ERP pagine PROFOND : le curseur n'est pas un raffinement, c'est la seule " +
                 "forme qui tienne à la millième page",
          warn: true,
          enfants: [
            { label: "la seule requête déclenchée — et elle porte déjà la portée",
              sql:
`SELECT m.comm_id, m.sujet, m.from_adresse, m.date_reception, m.nb_pieces_jointes
  FROM comm_tag mt JOIN comm m USING (comm_id)
 WHERE mt.tag_id = :tag
   AND m.boite_id = ANY (:portee_du_token)                     -- D37
   AND (m.date_reception, m.comm_id) < (:cur_date, :cur_id) -- curseur, pas OFFSET
 ORDER BY m.date_reception DESC, m.comm_id DESC
 LIMIT 20;`,
              index: "⚠ index (tag_id, date_reception DESC, comm_id DESC). La portée du " +
                     "token s'applique ICI, jamais dans l'appelant (D18/D37)", warn: true },
          ] },

        push: {
          label: "Notifier " + c.app + " (événement sortant)",
          kind: "api",
          sql:
`POST https://${c.app}.lan/api/atombox/hook          (asynchrone, rejouable)
{ "evenement": "message.tague", "comm_id": "…", "axe": "${tg.axe}",
  "valeur": "${tg.val}", "ref_externe": "${f.ref}", "pieces_jointes": ${m.pj} }`,
          index: "cet appel n'est PAS fait ici : il est empilé, et un worker le sortira. " +
                 "Une application injoignable ne doit jamais bloquer la réception du courrier",
          enfants: [
            { label: "tout ce qui se passe dans la transaction",
              sql:
`INSERT INTO evenement_sortant (application_id, type, charge, etat, prochaine_tentative)
VALUES (:app, 'message.tague', :json::jsonb, 'a_emettre', now());`,
              index: "index PARTIEL (prochaine_tentative) WHERE etat <> 'emis' — la file reste " +
                     "minuscule après des millions d'événements (D86)" },
          ] },
      }[quoi];
      ABX.log(E);
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Message = Message;
})(window.ABX = window.ABX || {});
