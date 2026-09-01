/* APPLICATIONS CONNECTÉES (D03 / D19 / D20 / D21).

   AtomBox porte le TAG et la RÉFÉRENCE EXTERNE, rien d'autre. Les montants
   ci-dessous sont ceux que l'application renverrait à l'affichage : dans le
   POC ils sont fabriqués, mais fabriqués de façon reproductible, pour que le
   cadre ne change pas de valeurs à chaque rechargement.

   Ce service est aussi celui qui rappelle, à chaque appel, que ce contexte
   n'est PAS stocké — c'est le premier besoin de cache du produit (Q31). */
(function (ABX) {
  "use strict";
  const P = ABX.PRNG;

  const APPS = {
    client:      { app:"dolibarr-mmi",  nom:"Dolibarr — MMI Négoce", ic:"🏢", pref:"TH",   objet:"tiers" },
    fournisseur: { app:"dolibarr-mmi",  nom:"Dolibarr — MMI Négoce", ic:"🏢", pref:"TH",   objet:"fournisseur" },
    sav:         { app:"redmine-ipro",  nom:"Redmine — support",     ic:"🛟", pref:"#",    objet:"demande" },
    partenaire:  { app:"nextcloud-mmi", nom:"Nextcloud — partage",   ic:"☁",  pref:"grp-", objet:"groupe" },
  };
  const PIECES = [["Devis","PR",["accepté","en attente","refusé"]],
                  ["Commande","CO",["expédiée","en préparation","validée"]],
                  ["Facture","FA",["payée","impayée","en retard"]]];
  const BON = { "payée":1, "accepté":1, "expédiée":1, "validée":1 };
  const MAUVAIS = { "impayée":1, "en retard":1, "refusé":1 };

  const cache = {};

  function fabrique(cfg) {
    const objets = [];
    for (let i = 0, n = P.int(2, 5); i < n; i++) {
      const p = P.pick(PIECES);
      objets.push({ type:p[0], statut:P.pick(p[2]), montant:P.int(120, 24000),
        ref: p[1] + "26" + String(P.int(1, 12)).padStart(2, "0") + "-" + String(P.int(1, 999)).padStart(4, "0") });
    }
    const du = objets.filter(o => o.type === "Facture" && o.statut !== "payée");
    return { cfg, ref: cfg.pref + P.int(1000, 9999), objets,
      encours: du.reduce((s, o) => s + o.montant, 0),
      echu: du.filter(o => o.statut === "en retard").reduce((s, o) => s + o.montant, 0),
      depuis: 2010 + P.int(0, 14) };
  }

  ABX.Erp = {
    APPS,
    statutClasse: o => BON[o.statut] ? "ok" : MAUVAIS[o.statut] ? "due" : "wait",
    /* Le tag d'un message qui relève d'une application connectée, s'il existe. */
    tagDe: m => (m.tags || []).find(t => APPS[t.axe]) || null,

    fiche(axe, val) {
      const k = axe + "|" + val;
      if (cache[k]) return cache[k];
      const cfg = APPS[axe];
      if (!cfg) return null;
      return cache[k] = P.with(k, () => fabrique(cfg));
    },
  };
})(window.ABX = window.ABX || {});
