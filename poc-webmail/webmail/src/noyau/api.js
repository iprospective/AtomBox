/* LA COUCHE D'ACCÈS — la seule porte entre l'interface et les données (D141).

   Les vues et les contrôleurs n'appellent JAMAIS le corpus ni le store des
   rattachements directement : ils appellent Api. Ce fichier ne contient que le
   CONTRAT — les noms, les paramètres, ce qui revient. L'implémentation est
   branchée à part :
     - api.http.js : l'implémentation UNIQUE — chaque opération est une route ;
       req() fait le fetch en prod, et route vers serveur.poc.js en POC.
   Le jour où l'API réelle existe, on retire serveur.poc.js, et rien d'autre.

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
    if (!impl) throw new Error("Api : aucune implémentation branchée (api.http.js)");
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
    /* l'arborescence de l'utilisateur : compteurs en UNE passe (D078), dossiers
       virtuels personnels (D143), épingles (D144) — GET /arborescence */
    compteurs:  () => appelle("compteurs", []),
    /* toutes les pièces jointes (page d'administration des blobs) */
    piecesJointes: () => appelle("piecesJointes", []),
    /* les RÉFÉRENTIELS de l'utilisateur connecté : ses boîtes, les dossiers
       spéciaux, ses dossiers, les axes et leurs valeurs, les statuts — GET /referentiels.
       Chargés une fois à l'amorçage, mis en cache dans ABX.Ref (lecture synchrone
       par les vues). Ce ne sont PAS des fixtures : c'est ce que le produit sert. */
    referentiels: () => appelle("referentiels", []),

    /* ---- la session (D063, D157) : POST /session rend un jeton ; DELETE le révoque */
    connecter:   (utilisateur, mot_de_passe) => appelle("connecter", [utilisateur, mot_de_passe]),
    deconnecter: () => appelle("deconnecter", []),

    /* ---- écriture : ce qui touche le RATTACHEMENT (D036) ------------------- */
    /* PATCH /messages/{id}/rattachement */
    patcher:    (id, patch) => appelle("patcher", [id, patch]),
    /* POST /messages — un message écrit ici (envoyé, brouillon) */
    creer:      m => appelle("creer", [m]),
    /* suppression définitive = détachement (D118) */
    detacher:   id => appelle("detacher", [id]),

    /* ---- écriture : l'arborescence de l'utilisateur ------------------------- */
    /* un dossier virtuel personnel : un filtre sans action (D075, D143) — POST /dossiers-virtuels */
    creerDossier:     d => appelle("creerDossier", [d]),
    /* DELETE /dossiers-virtuels/{id} — supprime la définition, jamais un message */
    supprimerDossier: id => appelle("supprimerDossier", [id]),
    /* un réglage personnel (D106, nature personnel) : les épingles (D144) — PUT /parametres */
    regler:           (cle, valeur) => appelle("regler", [cle, valeur]),

    /* ---- synchrone, par exception, et seulement pour ce qui est déjà en cache --
       Certaines vues rendent en une passe et ne peuvent pas attendre (compteur
       d'un nœud d'arborescence, titre d'un onglet). Elles lisent un cache que
       les appels asynchrones ont rempli. Le contrat le dit : ces deux-là peuvent
       rendre null, et la vue doit l'accepter ; les listes rendent [] tant que
       GET /arborescence n'a pas répondu. */
    cache: {
      message: id => impl && impl.cacheMessage ? impl.cacheMessage(id) : null,
      compteur: k => impl && impl.cacheCompteur ? impl.cacheCompteur(k) : null,
      virtuels: () => impl && impl.cacheVirtuels ? impl.cacheVirtuels() : [],
      epingles: () => impl && impl.cacheEpingles ? impl.cacheEpingles() : [],
    },
  };

  ABX.Api = Api;
})(window.ABX = window.ABX || {});
