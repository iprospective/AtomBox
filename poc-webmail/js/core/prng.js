/* Aléatoire DÉTERMINISTE — le corpus doit être identique d'une session à l'autre,
   sinon rien ne peut être persisté par delta (voir services/corpus.js). */
(function (ABX) {
  "use strict";
  let seed = 42;

  const PRNG = {
    next: () => (seed = seed * 16807 % 2147483647) / 2147483647,
    int:  (a, b) => a + Math.floor(PRNG.next() * (b - a + 1)),
    pick: a => a[Math.floor(PRNG.next() * a.length)],
    hex:  n => { let s = ""; while (s.length < n) s += "0123456789abcdef"[PRNG.int(0, 15)]; return s; },

    hash: t => { let h = 2166136261;
      for (let i = 0; i < t.length; i++) { h ^= t.charCodeAt(i); h = Math.imul(h, 16777619); }
      return (h >>> 0) % 2147483646 + 1; },

    /* Fabrique reproductible : même clé, même résultat, quel que soit l'ordre des clics.
       Sert aux données produites paresseusement (fiches ERP), qui doivent survivre
       à un rechargement sans être stockées. */
    with: (k, f) => { const g = seed; seed = PRNG.hash(k); const r = f(); seed = g; return r; },
  };

  ABX.PRNG = PRNG;
})(window.ABX = window.ABX || {});
