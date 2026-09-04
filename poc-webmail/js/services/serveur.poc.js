/* LE SERVEUR SIMULÉ — la seule chose qu'on jette (D141).

   Il reçoit ce que req() lui passe — méthode, chemin, corps — et répond
   comme le vrai serveur répondra : les MÊMES formes JSON, les mêmes codes.
   Derrière, il lit le corpus engendré et écrit le delta local ; mais
   l'interface ne le sait pas, et ne doit jamais le savoir.

   Chaque route est écrite ici EXPLICITEMENT (méthode + motif de chemin).
   Écrire le serveur réel, ce sera réécrire ce fichier dans son langage,
   route par route — c'est la spécification exécutable de l'API. */
(function (ABX) {
  "use strict";
  const C = ABX.Corpus, St = ABX.Store, T = ABX.Traces;

  /* ---- représentations : ce que le serveur SERT --------------------------
     L'objet du corpus porte EXACTEMENT les clés du contrat — celles du
     dictionnaire (sujet, from_nom, from_adresse, date_recue, nb_pieces_jointes,
     sorti_le, motif_sortie…). Le serveur le sert tel quel ; les clés « _ »
     (état de session) ne font pas partie du contrat et ne sortent jamais du
     vrai serveur. En POC on rend l'objet lui-même : le cache et le corpus ne
     font qu'un, ce qui est le comportement d'avant — sans plus aucun _m. */
  const rep = m => m;
  const ok = (extra) => Object.assign({ ok: true }, extra || {});

  const dossierDe = p => ({ id: p.dossier, kind: p.kind || (p.dossier && p.dossier.includes(":") ? "virtuel" : "special"), axe: p.axe });

  /* ---- les routes ----------------------------------------------------------- */
  const ROUTES = [
    ["GET", /^\/referentiels$/, () => { const Fx = ABX.Fixtures; return {
      moi: Fx.MOI, speciaux: Fx.SPECIAUX, util: Fx.UTIL, axes: Fx.AXES, valeurs: Fx.valeurs,
      statuts: Fx.STATUTS, vues: Object.keys(C.VUES) }; }],

    ["GET", /^\/arborescence$/, () => ({ compteurs: C.recompte() })],

    ["GET", /^\/messages$/, (_, p) => {
      const f = dossierDe(p);
      const l = p.tout ? C.vue(f) : C.filtrer(f, p.filtre, p.tri, p.sens, p.statut);
      return { messages: l.map(m => rep(m, false)), total: l.length }; }],

    ["GET", /^\/messages\/([^/]+)\/fil$/, (m) => { const x = C.par(dec(m[1])); if (!x) return null;
      return { messages: C.tous.filter(y => y.thread_id === x.thread_id && y.dossier_origine === x.dossier_origine)
        .sort((a, b) => a.date_recue - b.date_recue).map(y => rep(y, false)) }; }],

    ["GET", /^\/messages\/([^/]+)$/, (m) => { const x = C.par(dec(m[1])); return x ? rep(x, true) : null; }],

    ["GET", /^\/pieces-jointes$/, () => { const out = [];
      C.tous.forEach(m => (m.pieces_jointes || []).forEach((p, i) => out.push({ m, p, i })));
      return { pieces_jointes: out }; }],

    ["PATCH", /^\/messages\/([^/]+)\/rattachement$/, (m, _, corps) => {
      const x = C.par(dec(m[1])); if (!x) return null;
      St.patch(x, corps || {}); St.save();
      return ok({ modifies: 1, message: rep(x, false) }); }],

    ["POST", /^\/messages$/, (_, __, corps) => {
      C.ajoute(corps); St.crees.push(corps); St.save();
      return ok({ crees: 1, message: rep(corps, false) }); }],

    ["DELETE", /^\/messages\/([^/]+)\/rattachement$/, (m) => {
      const x = C.par(dec(m[1])); if (!x) return null;
      St.patch(x, { suppr: true }); C.retire(x); St.save();
      return ok({ modifies: 1, detache: true }); }],
  ];
  const dec = s => decodeURIComponent(s);

  function params(chemin) {
    const i = chemin.indexOf("?"); if (i < 0) return [chemin, {}];
    const p = {}; chemin.slice(i + 1).split("&").forEach(kv => { const [k, v] = kv.split("="); p[dec(k)] = dec(v || ""); });
    return [chemin.slice(0, i), p];
  }

  const ServeurSimule = {
    ROUTES,
    /* même contrat que fetch(...).then(r => r.json()) : un JSON, ou null pour 404 */
    traiter(methode, cheminBrut, corps) {
      const [chemin, p] = params(cheminBrut);
      for (const [meth, motif, fn] of ROUTES) {
        if (meth !== methode) continue;
        const m = chemin.match(motif); if (!m) continue;
        return fn(m, p, corps);
      }
      throw new Error("serveur simulé : route inconnue " + methode + " " + chemin);
    },
    routes: () => ROUTES.map(([m, r]) => m + " " + r.source.replace(/\\\//g, "/").replace(/\^|\$/g, "")),
  };
  ABX.ServeurSimule = ServeurSimule;
})(window.ABX = window.ABX || {});
