/* Bus d'événements — les services ne connaissent pas les vues.
   Un service mute l'état et émet ; les contrôleurs décident quoi repeindre. */
(function (ABX) {
  "use strict";
  const abonnes = {};
  /* ABX.log existe TOUJOURS, même sans journal des requêtes (mode produit, D141).
     query-log.js, quand il est chargé, la remplace par un vrai journal. Sans lui,
     un geste qui "logue" ne fait rien — et surtout ne casse pas. */
  ABX.log = ABX.log || function () {};

  ABX.Bus = {
    on:   (evt, fn) => { (abonnes[evt] = abonnes[evt] || []).push(fn); },
    emit: (evt, data) => { (abonnes[evt] || []).forEach(fn => fn(data)); },
  };
})(window.ABX = window.ABX || {});
