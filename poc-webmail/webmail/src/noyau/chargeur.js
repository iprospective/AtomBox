/* LE CHARGEUR — la liste fermée de D141, devenue une donnée du produit (D157).

   Il n'y a qu'un index.html. Quand la session est « poc » (poc/poc), ce fichier
   écrit les scripts du POC À LEUR PLACE, pendant l'analyse de la page, avec
   document.write : c'est synchrone et ordonné — les fichiers produit qui lisent
   le corpus ou les fixtures au chargement les trouvent, comme avant. Sans session
   « poc », aucun de ces fichiers n'est demandé : le produit est exactement ce
   que la page contient.

   Trois points d'écriture, parce que trois familles de dépendances :
     TETE     après le noyau — le générateur, le markdown, le journal, l'index du CDC ;
     DONNEES  après les services de base — les fixtures et le corpus lisent Fmt,
              Attachments, Store au chargement ;
     FIN      avant app.js — la surcouche CDC, les pages, les traces, le serveur
              simulé, la barre du POC.
   La page autonome (bundle) a tout inline : ABX_INLINE coupe l'écriture. La page
   produit (prod.html) n'embarque rien du POC : ABX_SANS_POC refuse poc/poc. */
(function (ABX) {
  "use strict";
  const TETE    = ["js/core/prng.js", "js/core/markdown.js", "js/services/query-log.js", "js/services/cdc-index.js"];
  const DONNEES = ["js/services/fixtures.js", "js/services/corpus.js"];
  const FIN     = ["js/views/contexte.cdc.js", "js/views/query-log.js", "js/views/pages.js",
                   "js/services/api-trace.js", "js/services/serveur.poc.js",
                   "js/controllers/pages.js", "js/poc/pocbar.js"];
  const Chargeur = {
    TETE, DONNEES, FIN,
    tout: () => TETE.concat(DONNEES, FIN),
    actif: () => ABX.Session.simulee() && !window.ABX_INLINE && !window.ABX_SANS_POC,
    ecrire(liste) {
      if (!Chargeur.actif()) return;
      const v = (document.querySelector('meta[name="abx-version"]') || {}).content;
      const q = v && v !== "dev" ? "?v=" + v : "";
      /* la balise est assemblée en deux morceaux : inline dans un bundle, la balise
         écrite en clair ferait croire à un script externe */
      document.write(liste.map(f => "<scr" + "ipt src=\"" + f + q + "\"></scr" + "ipt>").join("\n"));
    },
  };
  ABX.Chargeur = Chargeur;
  Chargeur.ecrire(TETE);
})(window.ABX = window.ABX || {});
