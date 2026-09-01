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
      el.querySelector("#dep").onchange = e => M.deplacer(m, e.target.value);

      D.on(el, "[data-x]", "onclick", b => M[b.dataset.x](m));
      D.on(el, "[data-c]", "onclick", b => ABX.Controllers.Compose.demarrer(b.dataset.c, m));
      D.on(el, "[data-a]", "onclick", b => Message.logMessage(b.dataset.a, m));
      D.on(el, ".pjc",     "onclick", c => Message.logPieceJointe(m, +c.dataset.pj));
      D.on(el, "[data-e]", "onclick", b => Message.logErp(m, b.dataset.e));
    },

    logMessage(quoi, m) {
      const A = {
        tag: ["Poser un tag",
`INSERT INTO message_tag (message_id, tag_id, source) VALUES (:id, :tag, :application)
 ON CONFLICT DO NOTHING;   -- pas d'unicité (message, axe) : deux clients possibles (D17)`,
          "ACL de l'axe vérifiée en amont (D18) ; axes autorisés injectés en axe_id IN (…)"],
        orig: ["Télécharger le message original (.eml)",
`-- réassemblage : le corps, puis chaque partie ré-encodée À L'IDENTIQUE (D25)
SELECT blob_ref, headers FROM message WHERE message_id = :id;
SELECT l.ordre, l.nom_fichier, l.mime_declare, l.transfer_encoding, l.disposition,
       l.parametres, p.blob_ref
  FROM message_piece_jointe l JOIN piece_jointe p USING (pj_id)
 WHERE l.message_id = :id ORDER BY l.ordre;`,
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
  FROM message_piece_jointe l JOIN piece_jointe p USING (pj_id)
 WHERE l.message_id = :id AND l.pj_id = ${b.pj_id};
-- les octets ne transitent jamais par PostgreSQL : zstd -d <blob_ref> (D05/D07)`,
        "index (message_id, ordre) sur la liaison — le fichier lui-même reste hors base");

      ABX.log("« " + p.nom + " » — qui d'autre porte CES octets ?",
`SELECT m.message_id, m.sujet, l.nom_fichier, m.date_reception
  FROM message_piece_jointe l JOIN message m USING (message_id)
 WHERE l.pj_id = ${b.pj_id}      -- ${b.refs} liaison(s) pour un seul blob de ${F.poids(b.ko)}
 ORDER BY m.date_reception DESC LIMIT 50;`,
        b.refs > 1
          ? "index (pj_id, message_id) — sans ce sens de parcours, la dédup n'est qu'un gain de " +
            "disque : ici elle économise " + F.poids(b.ko * (b.refs - 1)) +
            " et donne « où ai-je déjà vu ce fichier ? » (D24)"
          : "index (pj_id, message_id) — un seul porteur ici : sur ce fichier la dédup ne gagne " +
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
        res: ["Comment ce message a été rattaché à « " + tg.val + " »",
`-- 1. l'adresse pointe une IDENTITÉ, jamais l'inverse (D35)
SELECT c.correspondant_id, c.libelle
  FROM adresse a JOIN correspondant c USING (correspondant_id)
 WHERE a.adresse = lower('${m.mail}');        -- index UNIQUE (adresse)

-- 2. l'identité est reliée au tiers de CHAQUE application connectée
SELECT application_id, ref_externe FROM correspondant_externe
 WHERE correspondant_id = :cid;               -- ${c.app} → ${f.ref}

-- 3. c'est le CONNECTEUR qui pose le tag, pas AtomBox (D21)`,
          "un correspondant, N adresses : changer d'adresse ne coupe pas l'historique du tiers " +
          "(D35). Adresse inconnue ⇒ message sans tag : c'est voulu, pas un échec d'ingestion"],

        lie: ["Lier ce message à " + o.type.toLowerCase() + " " + o.ref,
`POST /api/v1/messages/{message_id}/tags        Authorization: Bearer <token ${c.app}>
{ "axe": "${tg.axe}", "valeur": "${tg.val}",
  "ref_externe": "${f.ref}", "piece": "${o.ref}" }

-- côté AtomBox
INSERT INTO tag (axe_id, application_id, valeur, ref_externe)
VALUES (:axe, :app, :valeur, :ref)
ON CONFLICT (axe_id, application_id, valeur) DO UPDATE
   SET ref_externe = EXCLUDED.ref_externe
RETURNING tag_id;
INSERT INTO message_tag (message_id, tag_id, pose_par, pose_le)
VALUES (:id, :tag, :application, now()) ON CONFLICT DO NOTHING;`,
          "l'application est DANS la clé d'unicité (axe, application, valeur) — D20 : quatre " +
          "Dolibarr font quatre jeux de tags et aucun n'écrase l'autre (D17). ACL de l'axe " +
          "vérifiée avant (D18)", false, "api"],

        inv: ["Onglet « Emails » de la fiche " + f.ref + ", vu depuis " + c.app,
`GET /api/v1/messages?axe=${tg.axe}&valeur=${encodeURIComponent(tg.val)}
    &application=${c.app}&limite=20&curseur=eyJkIjoiMjAyNi0wMy0xMSIsImkiOjkxfQ
Authorization: Bearer <token opaque de l'application>          -- D63

-- côté AtomBox
SELECT m.message_id, m.sujet, m.from_adresse, m.date_reception, m.nb_pieces_jointes
  FROM message_tag mt JOIN message m USING (message_id)
 WHERE mt.tag_id = :tag
   AND m.boite_id = ANY (:portee_du_token)                     -- D37
   AND (m.date_reception, m.message_id) < (:cur_date, :cur_id) -- curseur, pas OFFSET
 ORDER BY m.date_reception DESC, m.message_id DESC
 LIMIT 20;`,
          "⚠ index (tag_id, date_reception DESC, message_id DESC). Deux pièges : un ERP pagine " +
          "PROFOND (OFFSET interdit) et la portée du token s'applique ICI, jamais dans " +
          "l'appelant (D18/D37)", true, "api"],

        push: ["Notifier " + c.app + " (événement sortant)",
`POST https://${c.app}.lan/api/atombox/hook          (asynchrone, rejouable)
{ "evenement": "message.tague", "message_id": "…", "axe": "${tg.axe}",
  "valeur": "${tg.val}", "ref_externe": "${f.ref}", "pieces_jointes": ${m.pj} }

-- rien n'est émis dans la transaction d'ingestion : on empile, un worker vide
INSERT INTO evenement_sortant (application_id, type, charge, etat, prochaine_tentative)
VALUES (:app, 'message.tague', :json::jsonb, 'a_emettre', now());`,
          "index PARTIEL (prochaine_tentative) WHERE etat <> 'emis' — la file reste minuscule " +
          "après des millions d'événements, et une application injoignable ne bloque jamais la " +
          "réception", false, "api"],
      }[quoi];
      ABX.log(E[0], E[1], E[2], E[3], E[4]);
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Message = Message;
})(window.ABX = window.ABX || {});
