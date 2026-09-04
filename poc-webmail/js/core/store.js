/* ÉTAT ET PERSISTANCE.

   Le partage est celui du modèle, rendu littéral : le MESSAGE est un fait
   immuable — il est engendré, jamais stocké ; le RATTACHEMENT porte ce que le
   compte en a fait (lu, sorti de la file, déplacé, supprimé — D36/D30/D41), et
   lui seul va en localStorage. C'est pourquoi ce POC persiste quelques
   kilo-octets là où le corpus en pèse plusieurs méga. */
(function (ABX) {
  "use strict";
  const CLE = "abx.db.v2";

  const Store = {
    /* delta d'état : comm_id -> { lu, sorti, motif, dossier, suppr } */
    ratt: {},
    /* messages écrits ici : envoyés et brouillons — eux n'ont pas de fixture */
    crees: [],
    seq: 0,

    /* état d'interface, persisté pour retrouver la session telle qu'on l'a laissée */
    ui: {
      folder: { id:"inbox", label:"Boîte de réception", kind:"special" },
      filtre: "file", tri: "date_desc", sens: "tous", statut: "tous",
      navq: "", ouverts: {}, plus: {},
      /* Ordre des axes et tri interne de chacun : réglés par l'utilisateur,
         donc persistés. Une arborescence engendrée n'interdit pas de choisir
         son ordre — elle interdit seulement de le coder dans les noms. */
      ordreAxes: null, triAxe: {}, triFeat: "domaine", triFeatDesc: false,
      /* jalon simulé : 0 = la V0 (la V1 réduite, D140b), null = la maquette complète */
      jalon: null,
      tabs: [], tab: null,
    },

    charge() {
      let d = null;
      try { d = JSON.parse(localStorage.getItem(CLE) || "null"); } catch (e) {}
      if (!d || d.v !== 2) return null;
      Object.assign(this.ratt, d.ratt || {});
      (d.crees || []).forEach(m => this.crees.push(m));
      this.seq = d.seq || 0;
      ["folder","filtre","tri","sens","statut","ordreAxes","triAxe","jalon","triFeat","triFeatDesc"]
        .forEach(k => { if (d.ui && d.ui[k]) this.ui[k] = d.ui[k]; });
      if (d.ui) { this.ui.tabs = d.ui.tabs || []; this.ui.tab = d.ui.tab || null; }
      return d;
    },

    save() {
      try { localStorage.setItem(CLE, JSON.stringify({
        v: 2, seq: this.seq, ratt: this.ratt, crees: this.crees,
        ui: { folder: this.ui.folder, filtre: this.ui.filtre, tri: this.ui.tri,
              sens: this.ui.sens, statut: this.ui.statut,
              ordreAxes: this.ui.ordreAxes, triAxe: this.ui.triAxe, jalon: this.ui.jalon,
              triFeat: this.ui.triFeat, triFeatDesc: this.ui.triFeatDesc,
              tabs: this.ui.tabs, tab: this.ui.tab },
      })); } catch (e) { /* quota ou navigation privée : le POC reste utilisable */ }
    },

    /* Applique un patch au message ET au delta persisté, d'un seul geste :
       les deux ne peuvent pas diverger. */
    patch(m, p) { Object.assign(m, p); this.ratt[m.id] = { ...(this.ratt[m.id] || {}), ...p }; },

    tailleKo() {
      try { return Math.round((localStorage.getItem(CLE) || "").length / 102.4) / 10; }
      catch (e) { return 0; }
    },

    oublier() { try { localStorage.removeItem(CLE); } catch (e) {} },
  };

  ABX.Store = Store;
  /* La V0 (D140b) : tout ce que la V1 ajoute rend vide — la base existe, ses tables
     de V1 sont vides. Un seul test, partout. */
  ABX.V0 = () => Store.ui.jalon === 0;
})(window.ABX = window.ABX || {});
