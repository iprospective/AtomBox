/* Registre des VUES PARTIELLES, surchargeables par variante.
   Une partielle est une fonction (ctx) -> HTML. On l'enregistre sous un nom
   (« message.card »), et on peut en enregistrer une version spécialisée pour
   une variante (« message.card » + variante « sent »). La résolution prend la
   variante si elle existe, sinon la version de base.

   C'est ce qui permet d'afficher une notification autrement qu'un message de
   client SANS que la vue liste ait à connaître la différence. */
(function (ABX) {
  "use strict";
  const parts = {};
  const cle = (nom, variante) => variante ? nom + "@" + variante : nom;

  const Registry = {
    define: (nom, fn) => { parts[cle(nom)] = fn; },

    /* Version spécialisée. Reçoit le même ctx, plus ctx.base() pour appeler
       la version générique et l'enrichir plutôt que la réécrire. */
    defineFor: (nom, variante, fn) => { parts[cle(nom, variante)] = fn; },

    has: (nom, variante) => !!parts[cle(nom, variante)],

    render(nom, ctx) {
      const c = ctx || {};
      const fn = parts[cle(nom, c.variant)] || parts[cle(nom)];
      if (!fn) throw new Error("vue partielle inconnue : " + nom);
      if (parts[cle(nom)] && fn !== parts[cle(nom)])
        c.base = () => parts[cle(nom)](Object.assign({}, c, { base: null }));
      return fn(c);
    },

    /* ---- POINTS DE CONTEXTE (D142) --------------------------------------
       Un point de contexte est un endroit de l'interface où quelque chose
       peut s'expliquer. Il est nommé (« contexte.fiabilite.valide ») et VIDE
       par défaut. Des surcouches y branchent un contenu par MODE : « cdc » en
       POC (la décision, la règle, la requête), « aide » en prod (ce que
       l'utilisateur doit comprendre). Plusieurs modes peuvent être actifs ;
       on rend la concaténation. Un point sans contenu rend une chaîne vide —
       ce n'est pas une erreur, c'est le comportement normal en prod. */
    modes: [],
    contexte(point, ctx) {
      return Registry.modes.map(mode => parts[cle("contexte." + point, mode)])
        .filter(Boolean).map(fn => fn(ctx || {})).join("");
    },
    aContexte: point => Registry.modes.some(mode => !!parts[cle("contexte." + point, mode)]),
    /* la liste des points nommés quelque part, tous modes — sert au harnais */
    points: () => { const s = new Set();
      Object.keys(parts).forEach(k => { const m = k.match(/^contexte\.(.+)@(\w+)$/); if (m) s.add(m[1]); });
      return [...s].sort(); },
    pointsDuMode: mode => Object.keys(parts).filter(k => k.startsWith("contexte.") && k.endsWith("@" + mode))
      .map(k => k.slice(9, -(mode.length + 1))).sort(),

    /* Ce que le registre connaît — sert à la page de démonstration et au test. */
    liste: () => Object.keys(parts).sort(),
  };

  ABX.Registry = Registry;
})(window.ABX = window.ABX || {});
