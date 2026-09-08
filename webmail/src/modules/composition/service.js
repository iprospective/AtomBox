/* SERVICE DE COMPOSITION — nouveau message, réponse, transfert.

   Trois décisions se rejoignent ici, et l'écran doit les rendre visibles :
   — l'identité d'envoi par défaut est celle de la BOÎTE qui a reçu (Q026) ;
   — un transfert interne pose un LIEN, il ne recopie pas (D058/D067) ;
   — les destinataires internes sont livrés en base, sans passer par le SMTP (D012). */
(function (ABX) {
  "use strict";
  const St = ABX.Store, C = ABX.Corpus, Fx = ABX.Fixtures, At = ABX.Attachments;

  const cite = m => "\n\n\n— Le " + new Date(m.date_recue).toLocaleString("fr-FR") + ", " + m.from_nom +
    " a écrit :\n" + m.corps.split("\n").map(l => "> " + l).join("\n");

  const Compose = {
    /* Prépare le brouillon d'écran (pas encore un message). */
    preparer(mode, m) {
      const d = { mode, src: m ? m.id : null, cc:"", pieces_jointes:[], reference: mode === "tr" };
      if (mode === "new") {
        Object.assign(d, { de: (ABX.Ref.moi.boites[0] || {}).adresse || "", a:"", sujet:"", corps:"" });
      } else if (mode === "tr") {
        Object.assign(d, { de: m.boite, a:"",
          sujet: /^tr:/i.test(m.sujet) ? m.sujet : "Tr: " + m.sujet, corps: cite(m) });
      } else {
        const autres = (m.destinataires || []).filter(a => a !== m.boite);
        Object.assign(d, { de: m.boite,        // Q026 : l'identité de la BOÎTE, pas du compte
          a: m.from_adresse, cc: mode === "reptous" ? autres.join(", ") : "",
          sujet: /^re:/i.test(m.sujet) ? m.sujet : "Re: " + m.sujet, corps: cite(m) });
      }
      if (mode !== "new") ABX.log(mode === "tr" ? "Préparer un transfert" : "Préparer une réponse",
`-- l'identité d'envoi par défaut est celle de la BOÎTE qui a reçu, pas du compte
SELECT b.adresse, b.boite_id FROM rattachement r JOIN boite b USING (boite_id)
 WHERE r.comm_id = :id AND r.compte_id = :moi;`,
        mode === "tr"
          ? "un transfert interne ne recopie rien : il pose un lien + une ACL (D058/D067)"
          : "répondre depuis le compte et non depuis la boîte ampute le fil pour les collègues (Q026)");
      return d;
    },

    joindre(d) { d.pieces_jointes.push(At.simulee());
      ABX.log("Joindre un fichier",
`-- l'octet est haché AVANT d'être écrit : s'il existe déjà, on ne stocke rien
SELECT pj_id FROM piece_jointe WHERE sha256 = :sha;
INSERT INTO piece_jointe (sha256, octets, mime_detecte, blob_ref)
VALUES (:sha, :octets, :mime, :ref) ON CONFLICT (sha256) DO NOTHING RETURNING pj_id;`,
        "la déduplication vaut aussi à l'ÉMISSION (D024) — envoyer trois fois la même plaquette " +
        "n'écrit qu'un blob ; l'unicité sur sha256 est ce qui rend l'INSERT idempotent");
      return d;
    },

    fabriquer(d, fid) {
      const id = fid + "/u" + (++St.seq);
      const m = { id, dossier_origine: fid, sens: "out", from_nom: ABX.Ref.moi.nom, from_adresse: d.de, boite: d.de,
        destinataires: d.a.split(",").map(x => x.trim()).filter(Boolean),
        sujet: d.sujet || "(sans sujet)", corps: d.corps,
        snippet: (d.corps || "").split("\n").find(l => l.trim()) || "…",
        date_recue: Date.now(), lu: true, thread_id: 1000 + St.seq, tags: [],
        sorti_le: null, motif_sortie: null, dossier: null,
        pieces_jointes: d.pieces_jointes.slice(), reference: d.reference && d.src ? d.src : null, composition: null };
      /* Transfert par VALEUR : l'original est encapsulé, donc matérialisé (D066). */
      if (d.mode === "tr" && d.src && !d.reference) {
        const s = ABX.Api.cache.message(d.src);
        if (s) m.pieces_jointes.push(At.encapsuler(s));
      }
      At.recompter(m);
      m.taille = Math.max(4, Math.round((m.corps || "").length / 1024)) + Math.round(m.pj_ko * 1.37);
      return m;
    },

    /* Renvoie le message créé, ou null si l'envoi est refusé. */
    enregistrer(d, brouillonId, envoyer) {
      if (envoyer && !d.a.trim()) return null;
      /* Un brouillon réenregistré GARDE son identité (D089) : PUT, pas DELETE + POST. L'ancien
         chemin changeait l'identifiant à chaque enregistrement, et l'onglet ouvert pointait
         sur un message qui n'existait plus. */

      const m = Compose.fabriquer(d, envoyer ? "sent" : "drafts");
      if (!envoyer) m.composition = d;              // un brouillon se rouvre en composition
      /* la création passe par la couche d'accès (D141) : on rend la PROMESSE du
         message créé — l'appelant n'ouvre l'onglet qu'une fois la réponse là.
         Un brouillon déjà enregistré se MET À JOUR (PUT) : il garde son identifiant, donc
         son onglet ; il n'est recréé que s'il devient un envoi. */
      const reprise = brouillonId && !envoyer;
      if (reprise) m.id = brouillonId;
      const cree = (reprise ? ABX.Api.reenregistrer(brouillonId, m) : ABX.Api.creer(m))
        .then(() => { if (envoyer && brouillonId) return ABX.Api.detacher(brouillonId); })
        .then(() => ABX.Api.compteurs()).then(() => m);

      if (!envoyer) {
        ABX.log("Enregistrer le brouillon",
`INSERT INTO comm (comm_id, sujet, corps, brouillon, redige_par, maj_le)
VALUES (:id, :sujet, :corps, true, :moi, now())
ON CONFLICT (comm_id) DO UPDATE SET corps = EXCLUDED.corps, maj_le = now();`,
          "un brouillon est un message comme un autre, marqué : sinon il faut une seconde table " +
          "et deux chemins de code pour le même objet");
      } else {
        const dest = m.destinataires.concat(d.cc.split(",").map(x => x.trim()).filter(Boolean));
        const int = dest.filter(Fx.interne), ext = dest.filter(a => !Fx.interne(a));
        ABX.Traces.envoyer(m, d, int, ext);
      }
      ABX.Bus.emit("corpus:changed", { message: m });
      return cree;
    },
  };

  ABX.ComposeService = Compose;
})(window.ABX = window.ABX || {});
