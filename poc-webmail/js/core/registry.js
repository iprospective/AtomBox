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

    /* Ce que le registre connaît — sert à la page de démonstration et au test. */
    liste: () => Object.keys(parts).sort(),
  };

  ABX.Registry = Registry;
})(window.ABX = window.ABX || {});
