/* SERVICE DE COMPOSITION — nouveau message, réponse, transfert.

   Trois décisions se rejoignent ici, et l'écran doit les rendre visibles :
   — l'identité d'envoi par défaut est celle de la BOÎTE qui a reçu (Q26) ;
   — un transfert interne pose un LIEN, il ne recopie pas (D58/D67) ;
   — les destinataires internes sont livrés en base, sans passer par le SMTP (D12). */
(function (ABX) {
  "use strict";
  const St = ABX.Store, C = ABX.Corpus, Fx = ABX.Fixtures, At = ABX.Attachments;

  const cite = m => "\n\n\n— Le " + new Date(m.date).toLocaleString("fr-FR") + ", " + m.from +
    " a écrit :\n" + m.body.split("\n").map(l => "> " + l).join("\n");

  const Compose = {
    /* Prépare le brouillon d'écran (pas encore un message). */
    preparer(mode, m) {
      const d = { mode, src: m ? m.id : null, cc:"", pjs:[], ref: mode === "tr" };
      if (mode === "new") {
        Object.assign(d, { de: Fx.MOI.boites[0].adresse, a:"", sujet:"", corps:"" });
      } else if (mode === "tr") {
        Object.assign(d, { de: m.boite, a:"",
          sujet: /^tr:/i.test(m.subject) ? m.subject : "Tr: " + m.subject, corps: cite(m) });
      } else {
        const autres = (m.to || []).filter(a => a !== m.boite);
        Object.assign(d, { de: m.boite,        // Q26 : l'identité de la BOÎTE, pas du compte
          a: m.mail, cc: mode === "reptous" ? autres.join(", ") : "",
          sujet: /^re:/i.test(m.subject) ? m.subject : "Re: " + m.subject, corps: cite(m) });
      }
      if (mode !== "new") ABX.log(mode === "tr" ? "Préparer un transfert" : "Préparer une réponse",
`-- l'identité d'envoi par défaut est celle de la BOÎTE qui a reçu, pas du compte
SELECT b.adresse, b.boite_id FROM rattachement r JOIN boite b USING (boite_id)
 WHERE r.message_id = :id AND r.compte_id = :moi;`,
        mode === "tr"
          ? "un transfert interne ne recopie rien : il pose un lien + une ACL (D58/D67)"
          : "répondre depuis le compte et non depuis la boîte ampute le fil pour les collègues (Q26)");
      return d;
    },

    joindre(d) { d.pjs.push(At.simulee());
      ABX.log("Joindre un fichier",
`-- l'octet est haché AVANT d'être écrit : s'il existe déjà, on ne stocke rien
SELECT pj_id FROM piece_jointe WHERE sha256 = :sha;
INSERT INTO piece_jointe (sha256, octets, mime_detecte, blob_ref)
VALUES (:sha, :octets, :mime, :ref) ON CONFLICT (sha256) DO NOTHING RETURNING pj_id;`,
        "la déduplication vaut aussi à l'ÉMISSION (D24) — envoyer trois fois la même plaquette " +
        "n'écrit qu'un blob ; l'unicité sur sha256 est ce qui rend l'INSERT idempotent");
      return d;
    },

    fabriquer(d, fid) {
      const id = fid + "/u" + (++St.seq);
      const m = { id, fid, sens: "out", from: Fx.MOI.nom, mail: d.de, boite: d.de,
        to: d.a.split(",").map(x => x.trim()).filter(Boolean),
        subject: d.sujet || "(sans sujet)", body: d.corps,
        snippet: (d.corps || "").split("\n").find(l => l.trim()) || "…",
        date: Date.now(), lu: true, thread: 1000 + St.seq, tags: [],
        sorti: null, motif: null, dossier: null,
        pjs: d.pjs.slice(), ref: d.ref && d.src ? d.src : null, compo: null };
      /* Transfert par VALEUR : l'original est encapsulé, donc matérialisé (D66). */
      if (d.mode === "tr" && d.src && !d.ref) {
        const s = C.par(d.src);
        if (s) m.pjs.push(At.encapsuler(s));
      }
      At.recompter(m);
      m.size = Math.max(4, Math.round((m.body || "").length / 1024)) + Math.round(m.pj_ko * 1.37);
      return m;
    },

    /* Renvoie le message créé, ou null si l'envoi est refusé. */
    enregistrer(d, brouillonId, envoyer) {
      if (envoyer && !d.a.trim()) return null;
      const ancien = brouillonId ? C.par(brouillonId) : null;
      if (ancien) { St.patch(ancien, { suppr: true }); C.retire(ancien); }

      const m = Compose.fabriquer(d, envoyer ? "sent" : "drafts");
      if (!envoyer) m.compo = d;              // un brouillon se rouvre en composition
      St.crees.push(m); C.ajoute(m);
      C.recompte(); St.save();

      if (!envoyer) {
        ABX.log("Enregistrer le brouillon",
`INSERT INTO message (message_id, sujet, corps, brouillon, redige_par, maj_le)
VALUES (:id, :sujet, :corps, true, :moi, now())
ON CONFLICT (message_id) DO UPDATE SET corps = EXCLUDED.corps, maj_le = now();`,
          "un brouillon est un message comme un autre, marqué : sinon il faut une seconde table " +
          "et deux chemins de code pour le même objet");
      } else {
        const dest = m.to.concat(d.cc.split(",").map(x => x.trim()).filter(Boolean));
        const int = dest.filter(Fx.interne), ext = dest.filter(a => !Fx.interne(a));
        const enfants = [
          { label: "le message est écrit UNE fois, quel que soit le nombre de destinataires (D10)",
            sql:
`INSERT INTO message (message_id, sujet, corps, from_adresse, date_envoi, blob_ref)
VALUES (:id, :sujet, :corps, '` + d.de + `', now(), :ref);`,
            index: "le corps part au magasin d'octets, pas dans la colonne : la base indexe, " +
                   "elle ne stocke pas (D05/D07)" },
          { label: "l'expéditeur — sorti de la file dès l'écriture",
            sql:
`INSERT INTO rattachement (message_id, compte_id, boite_id, sens, recu_le, sorti_le, motif_sortie)
VALUES (:id, :moi, :boite, 'envoye', now(), now(), 'envoye');`,
            index: "le sens est posé ICI, à l'émission : c'est ce qui rend le filtre " +
                   "« reçus / envoyés » indexable au lieu d'être déduit de from_adresse" },
        ];
        if (int.length) enfants.push(
          { label: int.length + " destinataire(s) INTERNE(s) — livrés en base, sans SMTP (D12)",
            sql:
`INSERT INTO rattachement (message_id, compte_id, boite_id, sens, recu_le)
SELECT :id, b.compte_id, b.boite_id, 'recu', now() FROM boite b
 WHERE b.adresse = ANY (:internes);   -- ` + int.join(", "),
            index: "une ligne par destinataire, un seul message : c'est exactement ce que la " +
                   "déduplication devait donner (D10)" });
        if (d.ref && d.src) enfants.push(
          { label: "transfert par référence : un lien + une ACL, aucune copie (D58/D67)",
            sql:
`INSERT INTO message_lien (message_porteur, message_source, type)
VALUES (:id, '` + d.src + `', 'reference');
INSERT INTO acl_message (message_id, principal, droit, accorde_par)
SELECT '` + d.src + `', a, 'lire', :moi FROM unnest(:internes) a;`,
            index: "l'ACL est indépendante et durable (D60) : le destinataire garde l'accès même " +
                   "si l'expéditeur perd le sien" });
        if (ext.length) enfants.push(
          { label: ext.length + " destinataire(s) EXTERNE(s) — hors transaction",
            sql:
`COMMIT;
SELECT pg_notify('smtp_out', :id);   -- ` + ext.join(", "),
            index: int.length
              ? "⚠ destinataires MIXTES : le relais ne doit remettre QUE les externes, sinon " +
                "les internes reçoivent deux fois. C'est le point soulevé pour D12, et il se " +
                "règle au moment de l'envoi, pas dans Postfix"
              : "remise au relais après COMMIT : un SMTP lent ne doit pas tenir une transaction " +
                "ouverte",
            warn: int.length > 0 });

        ABX.log({
          label: "Envoyer — " + int.length + " interne(s), " + ext.length + " externe(s)",
          sql: "BEGIN;",
          warn: ext.length > 0 && int.length > 0,
          index: ext.length && int.length
            ? "⚠ le cas mixte est le seul vraiment délicat : une partie du message est livrée " +
              "en base, l'autre part au relais, et rien ne doit être livré deux fois"
            : ext.length
              ? "aucun destinataire interne : envoi SMTP classique, le message reste stocké une fois"
              : "aucun SMTP du tout : le message ne quitte jamais AtomBox (D12)",
          enfants });
      }
      ABX.Bus.emit("corpus:changed", { message: m });
      return m;
    },
  };

  ABX.ComposeService = Compose;
})(window.ABX = window.ABX || {});
