/* LA COUCHE D'ACCÈS — la seule porte entre l'interface et les données (D141).

   Les vues et les contrôleurs n'appellent JAMAIS le corpus ni le store des
   rattachements directement : ils appellent Api. Ce fichier ne contient que le
   CONTRAT — les noms, les paramètres, ce qui revient. L'implémentation est
   branchée à part :
     - api.poc.js  : lit le corpus engendré en mémoire, écrit le delta local ;
     - api.http.js : fera les requêtes HTTP avec le contrat de api-trace.js.
   Le jour où l'API réelle existe, on remplace un fichier, et rien d'autre.

   ASYNCHRONE PARTOUT, même quand la réponse est immédiate : une API simulée
   synchrone cache le seul problème d'interface que le produit aura — l'attente.
   Chaque méthode rend une promesse ; l'interface est écrite pour le vrai monde.

   Le journal des requêtes (POC) est un OBSERVATEUR de cette couche : il
   s'abonne à Api.on("appel", …) et n'est appelé à la main nulle part. */
(function (ABX) {
  "use strict";
  let impl = null;
  const abonnes = [];

  const appelle = (nom, args) => {
    if (!impl) throw new Error("Api : aucune implémentation branchée (api.poc.js ou api.http.js)");
    if (typeof impl[nom] !== "function") throw new Error("Api : opération inconnue " + nom);
    const t0 = Date.now();
    return Promise.resolve(impl[nom].apply(impl, args)).then(res => {
      abonnes.forEach(fn => { try { fn({ nom, args, res, ms: Date.now() - t0 }); } catch (e) {} });
      return res;
    });
  };

  const Api = {
    /* branchement d'une implémentation — une seule à la fois */
    brancher: i => { impl = i; },
    branchee: () => !!impl,
    on: fn => { abonnes.push(fn); },

    /* ---- lecture ---------------------------------------------------------- */
    /* la liste d'un dossier, filtrée et triée — GET /messages */
    liste:      (folder, filtre, tri, sens, statut) => appelle("liste", [folder, filtre, tri, sens, statut]),
    /* tout le contenu d'un dossier, sans filtre de liste — pour vider, compter */
    contenu:    folder => appelle("contenu", [folder]),
    /* un message — GET /messages/{id} */
    message:    id => appelle("message", [id]),
    /* le fil d'un message (thread_id matérialisé, D055) */
    fil:        m => appelle("fil", [m]),
    /* compteurs de l'arborescence, UNE passe (D078) — GET /arborescence */
    compteurs:  () => appelle("compteurs", []),
    /* toutes les pièces jointes (page d'administration des blobs) */
    piecesJointes: () => appelle("piecesJointes", []),
    /* les RÉFÉRENTIELS de l'utilisateur connecté : ses boîtes, les dossiers
       spéciaux, ses dossiers, les axes et leurs valeurs, les statuts — GET /referentiels.
       Chargés une fois à l'amorçage, mis en cache dans ABX.Ref (lecture synchrone
       par les vues). Ce ne sont PAS des fixtures : c'est ce que le produit sert. */
    referentiels: () => appelle("referentiels", []),

    /* ---- écriture : ce qui touche le RATTACHEMENT (D036) ------------------- */
    /* PATCH /messages/{id}/rattachement */
    patcher:    (id, patch) => appelle("patcher", [id, patch]),
    /* POST /messages — un message écrit ici (envoyé, brouillon) */
    creer:      m => appelle("creer", [m]),
    /* suppression définitive = détachement (D118) */
    detacher:   id => appelle("detacher", [id]),

    /* ---- synchrone, par exception, et seulement pour ce qui est déjà en cache --
       Certaines vues rendent en une passe et ne peuvent pas attendre (compteur
       d'un nœud d'arborescence, titre d'un onglet). Elles lisent un cache que
       les appels asynchrones ont rempli. Le contrat le dit : ces deux-là peuvent
       rendre null, et la vue doit l'accepter. */
    cache: {
      message: id => impl && impl.cacheMessage ? impl.cacheMessage(id) : null,
      compteur: k => impl && impl.cacheCompteur ? impl.cacheCompteur(k) : null,
    },
  };

  ABX.Api = Api;
})(window.ABX = window.ABX || {});
