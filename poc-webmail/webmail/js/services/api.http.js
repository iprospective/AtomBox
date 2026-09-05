/* L'IMPLÉMENTATION HTTP de la couche d'accès — la seule (D141).

   Chaque opération de Api est ici une ROUTE : méthode, chemin, paramètres,
   corps, et ce qu'on fait de la réponse. Tout passe par req(), l'unique
   fonction d'appel. En prod, req() fait le fetch. En POC, req() ne fait PAS
   l'appel : elle route vers ABX.ServeurSimule (serveur.poc.js), qui répond
   avec les MÊMES formes JSON que le vrai serveur répondra.

   C'est ce qui rend la frontière tenable : l'interface est écrite contre le
   contrat de réponse — {id, sujet, from_nom, from_adresse}, {ok, modifies} —
   jamais contre un objet interne du corpus. Le jour où le serveur existe, on
   retire serveur.poc.js de index.html, et rien d'autre. */
(function (ABX) {
  "use strict";
  const BASE = (ABX.config && ABX.config.api) || "/api/v1";
  const cache = { messages: {}, compteurs: {}, virtuels: [], epingles: [] };

  /* L'UNIQUE fonction d'appel. Simulée ou réelle, elle rend toujours une
     promesse de JSON — ou null sur 404 (hors portée = 404, jamais 403 : D108). */
  function req(methode, chemin, corps) {
    if (ABX.ServeurSimule)
      return Promise.resolve().then(() => ABX.ServeurSimule.traiter(methode, chemin, corps));
    return fetch(BASE + chemin, { method: methode,
      headers: { "Content-Type": "application/json", "Accept": "application/json" },
      body: corps === undefined ? undefined : JSON.stringify(corps) })
      .then(r => { if (r.status === 404) return null;
        if (!r.ok) throw new Error(methode + " " + chemin + " → " + r.status); return r.json(); });
  }
  const q = o => Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "")
    .map(([k, v]) => encodeURIComponent(k) + "=" + encodeURIComponent(v)).join("&");
  const garde = m => { if (m) cache.messages[m.id] = m; return m; };

  const ImplHttp = {
    /* ---- lecture --------------------------------------------------------- */
    liste: (folder, filtre, tri, sens, statut) =>
      req("GET", "/messages?" + q({ dossier: folder.id, kind: folder.kind, axe: folder.axe, filtre, tri, sens, statut }))
        .then(r => { const l = (r && r.messages) || []; l.forEach(garde); return l; }),
    contenu: folder =>
      req("GET", "/messages?" + q({ dossier: folder.id, kind: folder.kind, axe: folder.axe, tout: 1 }))
        .then(r => ((r && r.messages) || []).map(garde)),
    message: id => req("GET", "/messages/" + encodeURIComponent(id)).then(garde),
    fil: m => req("GET", "/messages/" + encodeURIComponent(m.id) + "/fil")
        .then(r => ((r && r.messages) || []).map(garde)),
    compteurs: () => req("GET", "/arborescence").then(r => {
      cache.compteurs = (r && r.compteurs) || {};
      cache.virtuels = (r && r.virtuels) || []; cache.epingles = (r && r.epingles) || [];
      return cache.compteurs; }),
    piecesJointes: () => req("GET", "/pieces-jointes").then(r => (r && r.pieces_jointes) || []),
    referentiels: () => req("GET", "/referentiels")
        .then(r => r || { moi: { nom: "", boites: [] }, speciaux: [], util: [], axes: [], valeurs: {}, statuts: [], vues: [] }),

    /* ---- écriture : réponses {ok, modifies, …} ------------------------------ */
    patcher: (id, patch) => req("PATCH", "/messages/" + encodeURIComponent(id) + "/rattachement", patch)
        .then(r => { if (r && r.message) garde(r.message); return r; }),
    creer: m => req("POST", "/messages", m).then(r => { if (r && r.message) garde(r.message); return r; }),
    detacher: id => req("DELETE", "/messages/" + encodeURIComponent(id) + "/rattachement")
        .then(r => { if (r && r.ok) delete cache.messages[id]; return r; }),

    /* ---- l'arborescence de l'utilisateur : {ok, crees|supprimes|modifies, …} --- */
    creerDossier: d => req("POST", "/dossiers-virtuels", d)
        .then(r => { if (r && r.dossier) cache.virtuels = cache.virtuels.concat([r.dossier]); return r; }),
    supprimerDossier: id => req("DELETE", "/dossiers-virtuels/" + encodeURIComponent(id))
        .then(r => { if (r && r.ok) { cache.virtuels = cache.virtuels.filter(v => v.id !== id);
                                    cache.epingles = cache.epingles.filter(e => e !== id); } return r; }),
    regler: (cle, valeur) => req("PUT", "/parametres", { cle, valeur, portee: "compte" })
        .then(r => { if (r && r.ok && cle === "epingles") cache.epingles = r.parametre.valeur; return r; }),

    /* ---- cache synchrone, pour les vues qui rendent en une passe ------------ */
    cacheMessage: id => cache.messages[id] || null,
    cacheCompteur: k => cache.compteurs[k] || { t: 0, u: 0, f: 0 },
    cacheVirtuels: () => cache.virtuels,
    cacheEpingles: () => cache.epingles,
  };

  ABX.Api.brancher(ImplHttp);
  ABX.ApiHttp = ImplHttp;
})(window.ABX = window.ABX || {});
