/* Harnais : charge les scripts DANS L'ORDRE DÉCLARÉ PAR index.html.
   Le test vérifie donc aussi que cet ordre est cohérent — une dépendance
   déplacée casse ici avant de casser dans le navigateur. */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const { creerDocument, creerStockage } = require("./fake-dom");

const RACINE = path.join(__dirname, "..");

function scriptsDeIndex() {
  const html = fs.readFileSync(path.join(RACINE, "index.html"), "utf8");
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
    setTimeout, clearTimeout, encodeURIComponent, Math, Date, JSON,
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

/* --- micro-cadre d'assertions ------------------------------------------- */
let ok = 0, ko = 0;
const eq = (a, b, quoi) => {
  if (a === b) { ok++; return; }
  ko++; console.log("  ✗ " + quoi + "\n      attendu " + JSON.stringify(b) + ", obtenu " + JSON.stringify(a));
};
const vrai = (c, quoi) => { if (c) ok++; else { ko++; console.log("  ✗ " + quoi); } };
const bilan = () => { console.log("\n" + ok + " assertion(s) passées, " + ko + " échec(s)");
                      process.exit(ko ? 1 : 0); };

module.exports = { demarrer, creerStockage, eq, vrai, bilan, RACINE };
