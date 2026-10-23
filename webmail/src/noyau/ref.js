/* RÉFÉRENTIELS — le cache synchrone de ce que Api.referentiels() a servi (D141).

   Les vues rendent en une passe et lisent ici : les boîtes de l'utilisateur,
   les dossiers spéciaux, ses dossiers, les axes et leurs valeurs, les statuts.
   Avant le premier chargement, tout est VIDE et les vues doivent rendre
   proprement avec rien — c'est ce que le harnais vérifie en mode produit.

   Ce fichier ne sait pas d'où viennent les données : fixtures en POC, API en
   prod. C'est la raison d'être de la couche. */
(function (ABX) {
  "use strict";
  const Ref = {
    moi: { nom: "", boites: [] },
    speciaux: [], util: [], axes: [], valeurs: {}, statuts: [], vues: [],
    charge: false,

    /* GET /referentiels → cache. Rend la promesse pour enchaîner la peinture. */
    charger() {
      return ABX.Api.referentiels().then(r => { Object.assign(Ref, r || {}); Ref.charge = true; return Ref; });
    },
    estAxe: id => Ref.axes.some(a => a.id === id),
    /* LES BOÎTES (D176). À une seule, rien ne s'affiche : la pastille et le filtre
       n'ont de sens qu'à partir de deux. Le RANG d'une boîte fixe sa couleur : il
       suit l'ordre servi, donc il est stable d'une session à l'autre. */
    plusieursBoites: () => (Ref.moi.boites || []).length > 1,
    rangBoite: adresse => (Ref.moi.boites || []).findIndex(b => b.adresse === adresse),
    /* LE FILTRE EN AMONT (D176 § 3) : les identifiants cochés, ou null pour « toutes ».
       Une boîte retirée depuis (accès révoqué) est oubliée ; une sélection qui n'en
       garde aucune, ou qui les garde toutes, vaut « toutes ». */
    boitesChoisies() {
      const toutes = (Ref.moi.boites || []).map(b => b.id);
      const ui = ABX.Store && ABX.Store.ui;
      const c = ((ui && ui.boites) || []).filter(id => toutes.includes(id));
      return c.length && c.length < toutes.length ? c : null;
    },
    estVue: id => Ref.vues.includes(id),
  };
  ABX.Ref = Ref;
})(window.ABX = window.ABX || {});
