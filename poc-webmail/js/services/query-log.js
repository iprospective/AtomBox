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

    /* Deux formes :
         add(label, sql, index, warn, kind)     — une requête, la forme courante ;
         add({ label, kind, sql, index, warn, enfants: [ { label, sql, index, warn } ] })

       La seconde sert dès qu'un geste en déclenche plusieurs : un appel d'API
       n'est pas une requête, c'est une requête qui EN PROVOQUE d'autres, et c'est
       précisément le coût qu'on veut voir. Un UPDATE suivi d'un INSERT dans le
       journal d'activité, de même. */
    add(a, sql, index, warn, kind) {
      const e = typeof a === "object" && a !== null
        ? { ...a, enfants: a.enfants || [] }
        : { label: a, sql, index, warn, kind, enfants: [] };
      e.t = new Date();
      entrees.unshift(e);
      if (entrees.length > MAX) entrees.pop();
      ABX.Bus.emit("querylog:changed");
    },
    vider() { entrees.length = 0; ABX.Bus.emit("querylog:changed"); },
  };

  /* Raccourci : ABX.log(...) est appelé des dizaines de fois. */
  ABX.log = (...a) => ABX.QueryLog.add(...a);
})(window.ABX = window.ABX || {});
