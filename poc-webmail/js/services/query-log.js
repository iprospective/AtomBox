/* LE JOURNAL DES REQUÊTES — le vrai livrable du POC (D79).
   Chaque geste de l'interface déclare la question qu'il pose aux données et
   l'index qu'elle suppose. C'est cette liste, pas les écrans, qui dictera le
   schéma. Un service, pas une vue : n'importe quelle couche peut journaliser. */
(function (ABX) {
  "use strict";
  const MAX = 40;
  const entrees = [];

  ABX.QueryLog = {
    entrees,
    /* kind : "sql" (défaut) ou "api" — un appel d'API n'est pas une requête interne. */
    add(label, sql, index, warn, kind) {
      entrees.unshift({ label, sql, index, warn, kind, t: new Date() });
      if (entrees.length > MAX) entrees.pop();
      ABX.Bus.emit("querylog:changed");
    },
    vider() { entrees.length = 0; ABX.Bus.emit("querylog:changed"); },
  };

  /* Raccourci : ABX.log(...) est appelé des dizaines de fois. */
  ABX.log = (...a) => ABX.QueryLog.add(...a);
})(window.ABX = window.ABX || {});
