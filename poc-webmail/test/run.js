/* Harnais : charge les scripts DANS L'ORDRE DÉCLARÉ PAR index.html.
   Le test vérifie donc aussi que cet ordre est cohérent — une dépendance
   déplacée casse ici avant de casser dans le navigateur. */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const { creerDocument, creerStockage } = require("./fake-dom");

const RACINE = path.join(__dirname, "..");

function scriptsDeIndex() {
  const html = fs.readFileSync(path.join(RACINE, process.env.ABX_INDEX || "index.html"), "utf8");
  return [...html.matchAll(/<script src="([^"]+)"><\/script>/g)].map(m => m[1]);
}

/* Démarre une « page » : nouveau contexte, même stockage si on veut simuler
   un rechargement. Renvoie le contexte pour piloter l'application. */
function demarrer(stockage) {
  const fichiers = scriptsDeIndex();
  const doc = creerDocument();
  const ls = stockage || creerStockage();
  const sandbox = {
    console, document: doc, localStorage: ls,
    matchMedia: () => ({ matches: false }),
    addEventListener: () => {}, alert: () => {}, confirm: () => true,
    location: { reload: () => {} },
    setTimeout, clearTimeout, encodeURIComponent, decodeURIComponent, Math, Date, JSON, Promise,
    /* pas de réseau dans le harnais : en mode produit sans serveur simulé, chaque
       appel rejette proprement — l'interface doit tenir avec une API qui répond
       « indisponible », c'est ce que le test du mode produit vérifie */
    fetch: () => Promise.reject(new Error("réseau indisponible dans le harnais")),
  };
  sandbox.window = sandbox;
  const ctx = vm.createContext(sandbox);
  for (const f of fichiers) {
    const code = fs.readFileSync(path.join(RACINE, f), "utf8");
    try { vm.runInContext(code, ctx, { filename: f }); }
    catch (e) { throw new Error("échec au chargement de " + f + " : " + e.message); }
  }
  return { ABX: sandbox.ABX, doc, ls, fichiers };
}

/* L'amorçage est ASYNCHRONE (D141 : les référentiels et la liste arrivent par
   promesse, même en POC). Un test qui lit le DOM juste après demarrer() lit
   une page pas encore peinte. drainer() vide la file des microtâches — c'est
   ce que fait le navigateur entre deux gestes — et rend la main quand ABX.pret
   est tenue. Les tests l'appellent : `await drainer(p)`. */
function drainer(p) {
  /* un amorçage qui REJETTE doit faire échouer le test, pas le suspendre :
     une promesse rejetée sans .catch, c'est un harnais qui attend 120 s */
  return new Promise((res, rej) => setImmediate(() =>
    (p.ABX.pret || Promise.resolve())
      .then(() => setImmediate(() => res(p)), e => rej(new Error("amorçage rejeté : " + (e && e.stack || e))))));
}

/* --- micro-cadre d'assertions ------------------------------------------- */
let ok = 0, ko = 0;
const eq = (a, b, quoi) => {
  if (a === b) { ok++; return; }
  ko++; console.log("  ✗ " + quoi + "\n      attendu " + JSON.stringify(b) + ", obtenu " + JSON.stringify(a));
};
const vrai = (c, quoi) => { if (c) ok++; else { ko++; console.log("  ✗ " + quoi); } };
const bilan = () => { console.log("\n" + ok + " assertion(s) passées, " + ko + " échec(s)");
                      process.exit(ko ? 1 : 0); };

module.exports = { demarrer, drainer, creerStockage, eq, vrai, bilan, RACINE };
