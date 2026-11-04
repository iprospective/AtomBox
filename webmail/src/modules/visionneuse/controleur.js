/* CONTRÔLEUR VISIONNEUSE (F154, D207, RM3630) — ouvrir, passer d'une pièce à l'autre, enregistrer, fermer.

   Les octets ne sont demandés qu'à l'AFFICHAGE d'une pièce, gardés le temps que la visionneuse est
   ouverte (revenir en arrière ne redemande rien), et LIBÉRÉS à sa fermeture : une URL d'objet
   non révoquée garde le fichier en mémoire jusqu'à la fermeture de l'onglet. */
(function (ABX) {
  "use strict";
  const D = ABX.Dom;

  const V = {
    ouverte: false, m: null, i: 0, cache: {},

    pieces() { return (V.m && V.m.pieces_jointes) || []; },

    ouvrir(m, i) {
      V.fermer(true);
      V.m = m; V.i = i || 0; V.ouverte = true;
      V.peindre();
      return V.charger();
    },

    /* les octets de la pièce courante — une fois par pièce et par ouverture */
    charger() {
      const i = V.i, m = V.m, p = V.pieces()[i];
      if (!p) return Promise.resolve(null);
      const g = ABX.Views.Visionneuse.genre(p.b && p.b.mime);
      if (V.cache[i] || g === "message" || g === "fichier") { V.peindre(); return Promise.resolve(V.cache[i] || null); }
      const pj = p.b && p.b.pj_id;
      if (!pj) { V.cache[i] = { erreur: true }; V.peindre(); return Promise.resolve(V.cache[i]); }
      return Promise.resolve(ABX.Api.contenuPieceJointe(m.id, pj)).then(blob => {
        if (V.m !== m) return null;                     // fermée, ou une autre ouverte entre-temps
        if (!blob) { V.cache[i] = { erreur: true }; V.peindre(); return V.cache[i]; }
        const e = { blob, url: null, texte: null };
        if (g === "texte" || g === "html") {
          const lire = blob.text ? Promise.resolve(blob.text()) : Promise.resolve(null);
          return lire.then(t => { e.texte = t == null ? null : String(t).slice(0, 500000); V.cache[i] = e; V.peindre(); return e; });
        }
        e.url = V.objetURL(blob);
        V.cache[i] = e; V.peindre(); return e;
      }).catch(() => { V.cache[i] = { erreur: true }; V.peindre(); return V.cache[i]; });
    },

    /* Isolé : le harnais n'a pas d'URL d'objet — ce qui n'est pas testable doit être petit. */
    objetURL(blob) {
      return typeof URL !== "undefined" && URL.createObjectURL && blob ? URL.createObjectURL(blob) : null;
    },
    liberer(url) { if (url && typeof URL !== "undefined" && URL.revokeObjectURL) URL.revokeObjectURL(url); },

    aller(d) {
      const n = V.pieces().length;
      if (!V.ouverte || n < 2) return Promise.resolve(null);
      V.i = (V.i + d + n) % n;
      V.peindre();
      return V.charger();
    },

    enregistrer() {
      const p = V.pieces()[V.i], e = V.cache[V.i];
      if (!p) return null;
      if (e && e.blob) return V.telecharger(e.blob, p.nom);
      const pj = p.b && p.b.pj_id;
      if (!pj) return null;
      return Promise.resolve(ABX.Api.contenuPieceJointe(V.m.id, pj)).then(b => b && V.telecharger(b, p.nom));
    },
    /* le navigateur enregistre : jamais une ouverture (une pièce HTML ouverte serait exécutée) */
    telecharger(blob, nom) {
      if (typeof URL === "undefined" || !URL.createObjectURL || typeof document === "undefined" || !document.createElement) return null;
      const url = URL.createObjectURL(blob), a = document.createElement("a");
      a.href = url; a.download = nom || "piece"; a.click();
      if (typeof setTimeout === "function") setTimeout(() => URL.revokeObjectURL(url), 30000);
      return url;
    },

    ouvrirMessage() {
      const p = V.pieces()[V.i];
      if (!p || !p.comm_id) return;
      V.fermer();
      ABX.Controllers.Tabs.ouvrir({ type: "msg", id: p.comm_id }, false);
    },

    fermer(silencieux) {
      Object.values(V.cache).forEach(e => V.liberer(e && e.url));
      V.cache = {}; V.ouverte = false; V.m = null;
      if (!silencieux) V.peindre();
    },

    /* ← → Échap, appelé par les raccourcis : tant qu'elle est ouverte, la visionneuse a le clavier */
    touche(k) {
      if (!V.ouverte) return false;
      if (k === "Escape") { V.fermer(); return true; }
      if (k === "ArrowLeft") { V.aller(-1); return true; }
      if (k === "ArrowRight") { V.aller(+1); return true; }
      return false;
    },

    peindre() {
      const el = D.byId("visionneuse"); if (!el) return;
      if (!V.ouverte) { el.innerHTML = ""; el.hidden = true; return; }
      const n = V.pieces().length;
      el.hidden = false;
      el.innerHTML = ABX.Views.Visionneuse.render({ piece: V.pieces()[V.i] || {}, entree: V.cache[V.i], i: V.i, n });
      D.on(el, "#vi_fermer", "onclick", () => V.fermer());
      D.on(el, "#vi_prec", "onclick", () => V.aller(-1));
      D.on(el, "#vi_suiv", "onclick", () => V.aller(+1));
      D.on(el, "#vi_enreg", "onclick", () => V.enregistrer());
      D.on(el, "#vi_enreg2", "onclick", () => V.enregistrer());
      D.on(el, "#vi_msg", "onclick", () => V.ouvrirMessage());
      // un clic sur le FOND (hors du cadre) ferme ; un clic dans le cadre, non
      D.on(el, "#vi_fond", "onclick", (n2, ev) => { if (!ev || ev.target === n2) V.fermer(); });
    },
  };

  ABX.Controllers = ABX.Controllers || {};
  ABX.Controllers.Visionneuse = V;
})(window.ABX = window.ABX || {});
