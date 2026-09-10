/* La feuille compilée est à jour : css/app.css == sass(src/app.scss). Sans node_modules, on le dit et on passe. */
"use strict";
const fs = require("fs"), path = require("path"), { execFileSync } = require("child_process");
const { eq, vrai, bilan, RACINE } = require("./run");
const sass = path.join(RACINE, "node_modules", ".bin", "sass");
console.log("— style : scss par module, un seul css ————————————");
const modules = fs.readdirSync(path.join(RACINE, "src", "modules")).filter(m => fs.existsSync(path.join(RACINE, "src", "modules", m, "_style.scss")));
vrai(modules.length >= 8, modules.length + " modules ont leur _style.scss");
const app = fs.readFileSync(path.join(RACINE, "src", "app.scss"), "utf8");
modules.forEach(m => vrai(app.includes('"modules/' + m + '/style"'), "app.scss importe " + m));
/* F044 — les quatre paliers, et le fait que le JS et le CSS parlent des MÊMES largeurs.
   Un seuil qui diverge entre la feuille de style et `MOBILE()` donne une interface à moitié
   basculée : les colonnes se replient, la navigation croit encore être sur un grand écran. */
{
  const css = fs.readFileSync(path.join(RACINE, "css", "app.css"), "utf8");
  const paliers = [...new Set([...css.matchAll(/@media \(max-width: (\d+)px\)/g)].map(m => +m[1]))].sort((a, b) => b - a);
  eq(paliers.join(","), "1240,980,760,480", "quatre paliers responsive, du plus large au plus étroit");
  const app = fs.readFileSync(path.join(RACINE, "src", "noyau", "application.js"), "utf8");
  const seuils = [...app.matchAll(/max-width:(\d+)px/g)].map(m => +m[1]);
  eq(seuils.join(","), "760,980", "MOBILE et TABLET reprennent deux de ces paliers, pas des largeurs à eux");
}

if (!fs.existsSync(sass)) { console.log("  (sass absent : npm install pour vérifier la fraîcheur de css/app.css)"); bilan(); }
else {
  const compile = execFileSync(sass, ["--no-source-map", "--style=expanded", path.join(RACINE, "src", "app.scss")], { encoding: "utf8" });
  const actuel = fs.readFileSync(path.join(RACINE, "css", "app.css"), "utf8");
  eq(compile.trim(), actuel.trim(), "css/app.css est la compilation à jour de src/app.scss (sinon : npm run css)");
  bilan();
}
