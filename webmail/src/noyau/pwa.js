/* L'APPLICATION INSTALLABLE (RM3251, D172) — enregistre le service worker, et rien d'autre.

   Chargé AVANT tout le reste, et indépendant d'ABX : l'amorçage s'arrête net sans session, or une
   application installée doit s'enregistrer même à l'écran de connexion. Hors d'un navigateur (le
   harnais) ou hors HTTPS, il ne fait rien — un service worker n'existe que sur une origine sûre —
   et une erreur ici ne doit JAMAIS empêcher le webmail de démarrer. */
(function () {
  "use strict";
  try {
    if (typeof navigator === "undefined" || !navigator.serviceWorker) return;
    var loc = typeof location !== "undefined" ? location : null;
    if (!loc || (loc.protocol !== "https:" && loc.hostname !== "localhost" && loc.hostname !== "127.0.0.1")) return;
    navigator.serviceWorker.register("sw.js").catch(function (e) { console.warn("service worker non enregistré :", e); });
  } catch (e) { /* jamais bloquant */ }
})();
