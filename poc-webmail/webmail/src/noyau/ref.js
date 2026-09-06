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
    estVue: id => Ref.vues.includes(id),
  };
  ABX.Ref = Ref;
})(window.ABX = window.ABX || {});
