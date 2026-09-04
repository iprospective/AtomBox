/* LA TRACE — le vrai livrable du POC (D079).

   Ce n'est plus un journal de requêtes SQL, c'est la **cascade complète** d'un
   geste : le clic, l'appel d'API, la route, le contrôleur, le service, les
   requêtes, la lecture du magasin d'octets, le JSON renvoyé, le rendu. C'est
   cette succession — et non les écrans — qui décrit ce qu'il faudra écrire.

   Une étape porte :
     t       le type (voir TYPES), qui décide du picto, de la couleur et du côté
     label   ce qui se passe
     detail  le contenu : code, SQL, JSON, signature de méthode
     index   l'index supposé (étapes SQL) ou la remarque de conception
     warn    true si l'étape est coûteuse, fragile ou non tranchée

   Trois formes d'appel sont acceptées, pour que le code existant reste valide :
     add(label, sql, index, warn, kind)
     add({ label, sql, index, warn, enfants: [...] })
     add({ label, etapes: [...] })                       ← la forme complète */
(function (ABX) {
  "use strict";
  const MAX = 25;
  const entrees = [];

  /* Le picto, le libellé de type, et le CÔTÉ : « c » client, « s » serveur.
     Le changement de côté est ce qui matérialise l'aller-retour réseau — le
     seul coût que la maquette ne peut pas simuler mais doit rendre visible. */
  const TYPES = {
    ui:     { ic:"🖱", nom:"interface",  cote:"c" },
    render: { ic:"🖼", nom:"rendu",      cote:"c" },
    cache:  { ic:"⚡", nom:"cache",      cote:"c" },
    http:   { ic:"↗",  nom:"requête",    cote:"r" },
    json:   { ic:"↙",  nom:"réponse",    cote:"r" },
    route:  { ic:"🧭", nom:"route",      cote:"s" },
    ctrl:   { ic:"🎛", nom:"contrôleur", cote:"s" },
    svc:    { ic:"⚙",  nom:"service",    cote:"s" },
    acl:    { ic:"🔒", nom:"portée",     cote:"s" },
    sql:    { ic:"🗄", nom:"SQL",        cote:"s" },
    blob:   { ic:"📦", nom:"magasin",    cote:"s" },
    event:  { ic:"📣", nom:"événement",  cote:"s" },
    note:   { ic:"💬", nom:"note",       cote:"s" },
  };

  /* Ramène les anciennes formes à une suite d'étapes. */
  function normaliser(a, sql, index, warn, kind) {
    if (typeof a === "object" && a !== null) {
      if (a.etapes) return { label: a.label, etapes: a.etapes };
      const etapes = [];
      if (a.sql) etapes.push({ t: a.kind === "api" ? "http" : "sql",
                               detail: a.sql, index: a.index, warn: a.warn });
      else if (a.index) etapes.push({ t:"note", detail: a.index });
      (a.enfants || []).forEach(e => etapes.push({
        t: e.kind === "api" ? "http" : "sql",
        label: e.label, detail: e.sql, index: e.index, warn: e.warn }));
      return { label: a.label, etapes };
    }
    return { label: a, etapes: [{ t: kind === "api" ? "http" : "sql",
                                  detail: sql, index, warn }] };
  }

  ABX.QueryLog = {
    entrees, TYPES,
    add(a, sql, index, warn, kind) {
      const e = normaliser(a, sql, index, warn, kind);
      e.t = new Date();
      e.warn = e.etapes.some(x => x.warn);
      entrees.unshift(e);
      if (entrees.length > MAX) entrees.pop();
      ABX.Bus.emit("querylog:changed");
    },
    vider() { entrees.length = 0; ABX.Bus.emit("querylog:changed"); },
  };

  ABX.log = (...a) => ABX.QueryLog.add(...a);
})(window.ABX = window.ABX || {});
