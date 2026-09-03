/* Le bundle doit se comporter exactement comme les sources : même corpus, mêmes
   vues, même trace. Sinon le fichier déployé n'est pas ce qu'on a testé. */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const { creerDocument, creerStockage } = require("./fake-dom");
const { demarrer, eq, vrai, bilan } = require("./run");

const RACINE = path.join(__dirname, "..");
const BUNDLE = path.join(RACINE, "dist", "index.html");

if (!fs.existsSync(BUNDLE)) {
  console.log("dist/index.html absent — lancer : python3 outils/bundle.py");
  process.exit(1);
}
const html = fs.readFileSync(BUNDLE, "utf8");

console.log("— forme du bundle ————————————————————————————");
eq((html.match(/<script src=/g) || []).length, 0, "aucun script externe");
eq(html.includes("css/app.css"), false, "aucune feuille de style externe");
vrai(html.includes("<style>"), "la feuille est inlinée");
vrai(html.includes("engendrée par outils/bundle.py"), "le fichier se déclare engendré");
vrai(html.length > 150000, "taille : " + Math.round(html.length / 1024) + " Ko");

console.log("— il tourne ——————————————————————————————————");
/* Le bundle ne contient qu'UN bloc script, mais son contenu peut citer la
   chaîne « <script> » (le CDC parle d'affichage sûr) : on prend du premier
   <script> au DERNIER </script>, pas au premier venu. */
const js = html.slice(html.indexOf("<script>") + 8, html.lastIndexOf("</script>"));
const doc = creerDocument(), ls = creerStockage();
const sandbox = { console: { log(){}, warn(){}, error(){} }, document: doc, localStorage: ls,
  matchMedia: () => ({ matches:false }), addEventListener: () => {},
  alert: () => {}, confirm: () => true, location: { reload(){} },
  setTimeout, clearTimeout, encodeURIComponent, Math, Date, JSON };
sandbox.window = sandbox;
vm.runInContext(js, vm.createContext(sandbox), { filename: "dist/index.html" });
const B = sandbox.ABX;

console.log("— même comportement que les sources ————————————");
const src = demarrer(creerStockage()).ABX;
eq(B.Corpus.tous.length, src.Corpus.tous.length,
   "même corpus (" + B.Corpus.tous.length + " messages)");
eq(B.Registry.liste().length, src.Registry.liste().length, "mêmes vues partielles");
eq(Object.keys(B.Providers.CAPACITES).length, Object.keys(src.Providers.CAPACITES).length,
   "mêmes capacités");
eq(B.CDC.decisions.length, src.CDC.decisions.length, "même index du CDC");
vrai(doc.getElementById("nav").innerHTML.includes("Fournisseurs"), "l'arborescence est peinte");
vrai(doc.getElementById("list").innerHTML.includes("msg"), "la liste aussi");
vrai(doc.getElementById("qpanel").innerHTML.includes("casc"), "et la trace");

bilan();
