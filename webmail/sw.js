/* LE SERVICE WORKER (RM3251, D172) — il rend AtomBox installable sur un téléphone, et il dit « pas
   de réseau » au lieu d'une page blanche. C'est TOUT ce qu'il fait.

   Il ne met AUCUNE page de l'application en cache : un service worker qui garde l'ancien webmail
   est un service worker qui empêche une livraison d'arriver jusqu'au téléphone — et l'on ne s'en
   aperçoit qu'en se demandant pourquoi un correctif « ne marche pas ». Il n'intercepte donc que les
   NAVIGATIONS, réseau d'abord, et ne répond lui-même qu'en l'absence de réseau. L'API, les scripts,
   les feuilles de style passent sans qu'il les touche.

   Mettre le courrier en cache pour le lire hors ligne est un autre chantier, avec d'autres
   questions (quoi garder, combien, et le chiffrement d'un appareil qu'on perd). Pas celui-ci. */
"use strict";
const VERSION = "dev";                              // estampillée à chaque livraison (outils/deploy.sh)
const CACHE = "atombox-hors-ligne-" + VERSION;
const HORS_LIGNE = "hors-ligne.html";

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.add(HORS_LIGNE)).then(() => self.skipWaiting()));
});

/* une nouvelle version prend la main tout de suite, et emporte les caches des anciennes */
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys()
    .then(cles => Promise.all(cles.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});

self.addEventListener("fetch", e => {
  if (e.request.mode !== "navigate") return;       // tout le reste : le navigateur, comme sans nous
  e.respondWith(fetch(e.request).catch(() => caches.match(HORS_LIGNE)));
});
