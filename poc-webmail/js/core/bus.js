/* Bus d'événements — les services ne connaissent pas les vues.
   Un service mute l'état et émet ; les contrôleurs décident quoi repeindre. */
(function (ABX) {
  "use strict";
  const abonnes = {};
  ABX.Bus = {
    on:   (evt, fn) => { (abonnes[evt] = abonnes[evt] || []).push(fn); },
    emit: (evt, data) => { (abonnes[evt] || []).forEach(fn => fn(data)); },
  };
})(window.ABX = window.ABX || {});
