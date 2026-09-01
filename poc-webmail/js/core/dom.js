/* Accès au DOM — volontairement minimal : les vues produisent du HTML,
   les contrôleurs câblent les événements. */
(function (ABX) {
  "use strict";
  const byId = id => document.getElementById(id);

  ABX.Dom = {
    byId,
    /* Écrit une vue dans un conteneur et rend le conteneur pour le câblage. */
    paint: (id, html) => { const el = byId(id); el.innerHTML = html; return el; },
    /* Délégation : un seul écouteur par conteneur, quel que soit le nombre de lignes. */
    on: (root, sel, evt, fn) => root.querySelectorAll(sel).forEach(el => el[evt] = e => fn(el, e)),
    /* Ferme un clic sur l'élément porteur de l'attribut, ou null. */
    closest: (e, attr) => e.target.closest("[" + attr + "]"),
  };
})(window.ABX = window.ABX || {});
