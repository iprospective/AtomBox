/* L'APPLICATION INSTALLABLE (RM3251, D172) — ce qui fait qu'un téléphone propose « Installer
   AtomBox », et ce qui garantit qu'une fois installée, elle reçoit encore les livraisons.

   Le piège d'un service worker n'est pas de ne pas marcher : c'est de marcher TROP — garder en cache
   l'ancien webmail, et qu'aucun correctif n'arrive plus jusqu'au téléphone sans qu'on sache pourquoi.
   Ce harnais fait donc tourner sa logique pour de vrai, dans un faux navigateur, et vérifie autant
   ce qu'il ne doit PAS faire que ce qu'il fait. */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const { eq, vrai, bilan, RACINE } = require("./run");
const liste = a => JSON.stringify(Array.from(a));       // `eq` compare par identité : on compare le CONTENU

console.log("— le manifeste : ce que Chrome exige pour proposer l'installation ——");
const man = JSON.parse(fs.readFileSync(path.join(RACINE, "manifest.webmanifest"), "utf8"));
vrai(man.name && man.short_name, "un nom, et un nom court pour l'écran d'accueil");
eq(man.display, "standalone", "l'application s'ouvre en plein écran, sans barre d'adresse");
vrai(man.start_url && man.scope, "une adresse de départ et une portée");
const dims = f => { const b = fs.readFileSync(path.join(RACINE, f));   // l'en-tête IHDR d'un PNG
  return b.slice(1, 4).toString() === "PNG" ? b.readUInt32BE(16) + "x" + b.readUInt32BE(20) : null; };
for (const ic of man.icons) {
  vrai(fs.existsSync(path.join(RACINE, ic.src)), "l'icône " + ic.src + " existe");
  eq(dims(ic.src), ic.sizes, ic.src + " fait vraiment " + ic.sizes + " — une taille déclarée fausse est refusée");
}
vrai(man.icons.some(i => i.sizes === "192x192") && man.icons.some(i => i.sizes === "512x512"),
     "192 et 512 px : les deux tailles sans lesquelles Chrome ne propose rien");
vrai(man.icons.some(i => i.purpose === "maskable"),
     "une icône « maskable » : sans elle, Android pose l'icône rétrécie sur un fond blanc");

console.log("— la page : elle déclare l'application, et l'enregistre avant tout ————");
const index = fs.readFileSync(path.join(RACINE, "index.html"), "utf8");
vrai(index.includes('<link rel="manifest" href="manifest.webmanifest">'), "index.html déclare le manifeste");
vrai(/<meta name="theme-color"/.test(index), "et la couleur de la barre système");
const iPwa = index.indexOf("src/noyau/pwa.js"), iAmorce = index.indexOf("src/noyau/amorcage.js");
vrai(iPwa > 0 && iPwa < iAmorce, "pwa.js est chargé AVANT l'amorçage — qui s'arrête net sans session");

console.log("— l'enregistrement : jamais bloquant, jamais hors HTTPS ——————————————");
const pwa = fs.readFileSync(path.join(RACINE, "src/noyau/pwa.js"), "utf8");
const enregistrer = (loc, nav) => { const vus = [];
  const ctx = { console: { warn() {} }, location: loc,
    navigator: nav === undefined ? { serviceWorker: { register: u => { vus.push(u); return Promise.resolve(); } } } : nav };
  vm.runInNewContext(pwa, ctx); return vus; };
eq(liste(enregistrer({ protocol: "https:", hostname: "atombox.exemple.fr" })), liste(["sw.js"]), "en HTTPS : le service worker est enregistré");
eq(liste(enregistrer({ protocol: "http:", hostname: "atombox.exemple.fr" })), "[]", "hors HTTPS : rien — un service worker n'y existe pas");
eq(liste(enregistrer({ protocol: "https:", hostname: "x" }, null)), "[]", "sans navigator (le harnais) : rien, et aucune erreur");
eq(liste(enregistrer({ protocol: "https:", hostname: "x" }, { serviceWorker: { register() { throw new Error("refusé"); } } })), "[]",
   "un refus du navigateur ne remonte pas : il ne doit jamais empêcher le webmail de démarrer");

console.log("— le service worker : hors ligne oui, ancienne version jamais ——————————");
function sw() {
  const ecoute = {}, caches = {}, supprimes = [];
  const self = { addEventListener: (t, f) => { ecoute[t] = f; }, skipWaiting: () => Promise.resolve(),
                 clients: { claim: () => Promise.resolve() } };
  const api = {
    open: n => Promise.resolve({ add: u => { (caches[n] = caches[n] || new Set()).add(u); return Promise.resolve(); } }),
    keys: () => Promise.resolve(Object.keys(caches)),
    delete: n => { supprimes.push(n); delete caches[n]; return Promise.resolve(true); },
    match: u => Promise.resolve(Object.values(caches).some(c => c.has(u)) ? "PAGE HORS LIGNE" : undefined),
  };
  let reseau = true;
  const ctx = { self, caches: api, fetch: () => reseau ? Promise.resolve("RÉPONSE DU RÉSEAU") : Promise.reject(new TypeError("réseau")) };
  vm.runInNewContext(fs.readFileSync(path.join(RACINE, "sw.js"), "utf8"), ctx);
  const evt = req => { let rep = null, attente = null;
    return { request: req, respondWith: p => { rep = p; }, waitUntil: p => { attente = p; },
             get reponse() { return rep; }, get attente() { return attente; } }; };
  return { ecoute, caches, supprimes, evt, coupe: () => { reseau = false; } };
}
(async () => {
  const s = sw();
  const inst = s.evt(); s.ecoute.install(inst); await inst.attente;
  const gardes = [].concat(...Object.values(s.caches).map(c => [...c]));
  eq(liste(gardes), liste(["hors-ligne.html"]), "à l'installation, il ne garde QUE la page hors ligne — aucune page du webmail");

  s.caches["atombox-hors-ligne-ancienne"] = new Set(["index.html"]);          // la trace d'une livraison passée
  const act = s.evt(); s.ecoute.activate(act); await act.attente;
  eq(liste(s.supprimes), liste(["atombox-hors-ligne-ancienne"]), "une nouvelle version emporte les caches des anciennes");

  const nav = s.evt({ mode: "navigate", url: "https://a/" }); s.ecoute.fetch(nav);
  eq(await nav.reponse, "RÉPONSE DU RÉSEAU", "une navigation va au RÉSEAU d'abord : la livraison du jour arrive");
  for (const [mode, quoi] of [["cors", "l'API"], ["no-cors", "un script"], ["same-origin", "une feuille de style"]]) {
    const e = s.evt({ mode, url: "https://a/x" }); s.ecoute.fetch(e);
    eq(e.reponse, null, quoi + " passe sans que le service worker la touche — ni cache, ni réponse à sa place");
  }
  s.coupe();
  const horsLigne = s.evt({ mode: "navigate", url: "https://a/" }); s.ecoute.fetch(horsLigne);
  eq(await horsLigne.reponse, "PAGE HORS LIGNE", "sans réseau : « pas de réseau », pas une page blanche");

  console.log("— la page hors ligne tient SEULE ———————————————————————————————————");
  const hl = fs.readFileSync(path.join(RACINE, "hors-ligne.html"), "utf8");
  vrai(!/<script[^>]+src=|<link[^>]+rel="stylesheet"/.test(hl), "elle ne charge rien : ni script, ni feuille de style externe");
  vrai(hl.includes("location.reload()"), "et elle propose de réessayer");
  bilan();
})();
