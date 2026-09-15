/* LA COUVERTURE DU MODE PRODUIT (RM3189) — le contrôle qui refuse un bouton non testé.

   Écrire des tests ne suffit pas : ils vieillissent. Ce fichier inventorie ce que l'interface
   PROPOSE — chaque contrôle nommé, chaque geste, chaque fonction publique — et vérifie qu'un
   parcours du mode produit l'exerce (`test/prod.js`, `test/parcours.js`).

   Pourquoi le mode produit : les sept défauts trouvés à l'usage les 14 et 15 septembre étaient
   tous couverts par la maquette et jamais exercés en `api`. Ce qui n'est testé qu'en maquette
   n'est pas testé.

   LA DETTE. Tout n'est pas couvert aujourd'hui, et prétendre le contraire serait faux. Ce qui
   ne l'est pas est inscrit NOMINATIVEMENT dans `couverture.dette.json`, et cette liste ne peut
   que rétrécir : un nom qui n'y est pas et qui n'est pas exercé fait échouer le contrôle. C'est
   ce qui empêche d'ajouter un bouton sans son parcours, sans exiger d'écrire cent tests ce soir.
   Quand un ticket couvre un de ces noms, le contrôle le dit et la liste se réduit d'autant —
   une dette qui ment est une dette qu'on cesse de lire.

       node test/couverture.js           vérifie
       node test/couverture.js --figer   réécrit la référence (à faire sciemment, jamais pour
                                         faire taire un rouge) */
"use strict";
const fs = require("fs"), path = require("path");
const { eq, vrai, bilan, RACINE } = require("./run");

const DETTE = path.join(RACINE, "test", "couverture.dette.json");
const FIGER = process.argv.includes("--figer");

const PARCOURS = ["prod.js", "parcours.js"]
  .map(f => fs.readFileSync(path.join(RACINE, "test", f), "utf8")).join("\n");

/* Deux familles d'exceptions STRUCTURELLES — elles ne sont pas de la dette, elles n'ont pas
   lieu d'être exercées ici. Tout le reste est de la dette, nommée. */
const RENDU = ["render", "decrire", "statutHtml", "menuHtml", "fiabiliteHtml", "repondHtml",
               "spoofHtml", "lienHtml", "titre", "tailleKo", "contexte"];   // exercés par le rendu
const POC = ["log", "logFiltre", "logSens", "logMessage", "logErp", "logPieceJointe", "logTri",
             "logOuverture", "logRestauration", "logCompteurs", "encapsuler", "fiche", "choisir",
             "creerTache", "ficheContact", "actif", "deposerFichier", "ecrire"];  // maquette seule
const CONTROLES_POC = ["qpanel", "qn", "qclr"];        // le journal des requêtes n'existe qu'en POC

/* ---- l'inventaire ----------------------------------------------------------------------- */
const sources = [];
(function scan(d) {
  for (const e of fs.readdirSync(d, { withFileTypes: true })) {
    const p = path.join(d, e.name);
    if (e.isDirectory()) { if (e.name !== "poc") scan(p); }
    else if (e.name.endsWith(".js")) sources.push(p);
  }
})(path.join(RACINE, "src"));
const contenu = sources.map(p => fs.readFileSync(p, "utf8")).join("\n");

const uniq = a => [...new Set(a)].sort();
const controles = uniq([...contenu.matchAll(/id="([a-z0-9_\-]+)"/g)].map(m => m[1]))
  .filter(c => !CONTROLES_POC.includes(c));
const gestes = uniq([...contenu.matchAll(/data-(?:act|vol|adm|cap)="([a-z_]+)"/g)].map(m => m[1]));
const fonctions = uniq([...contenu.matchAll(/^\s{4}([a-zA-Zé]\w*)\(/gm)].map(m => m[1]))
  .filter(f => !RENDU.includes(f) && !POC.includes(f));

const cite = nom => PARCOURS.includes('"' + nom + '"') || PARCOURS.includes("'" + nom + "'")
                 || PARCOURS.includes("#" + nom) || new RegExp("\\b" + nom + "\\s*\\(").test(PARCOURS);

const nonExerces = {
  controles: controles.filter(c => !cite(c)),
  gestes: gestes.filter(g => !cite(g)),
  fonctions: fonctions.filter(f => !cite(f)),
};

if (FIGER) {
  fs.writeFileSync(DETTE, JSON.stringify(nonExerces, null, 1) + "\n");
  console.log("référence figée : %d contrôle(s), %d geste(s), %d fonction(s) non exercés",
              nonExerces.controles.length, nonExerces.gestes.length, nonExerces.fonctions.length);
  process.exit(0);
}

const dette = JSON.parse(fs.readFileSync(DETTE, "utf8"));
console.log("— couverture du mode produit (RM3189) ————————————————");
for (const [k, tout] of [["controles", controles], ["gestes", gestes], ["fonctions", fonctions]]) {
  const reste = nonExerces[k].length;
  console.log("  " + k.padEnd(10) + " : " + tout.length + " inventoriés, "
              + (tout.length - reste) + " exercés, " + reste + " en dette");
}

for (const k of ["controles", "gestes", "fonctions"]) {
  const neufs = nonExerces[k].filter(x => !dette[k].includes(x));
  eq(neufs.length, 0, "aucun élément NEUF sans parcours produit (" + k + ")"
     + (neufs.length ? " — à couvrir : " + neufs.join(", ") : ""));
}
const resorbes = ["controles", "gestes", "fonctions"]
  .flatMap(k => dette[k].filter(x => !nonExerces[k].includes(x)));
if (resorbes.length) console.log("  ↓ dette résorbée (%d) : node test/couverture.js --figer", resorbes.length);
eq(resorbes.length, 0, "la référence correspond au réel — une dette qui ment est une dette qu'on cesse de lire");

vrai(RENDU.length + POC.length + CONTROLES_POC.length < 40,
     "les exceptions structurelles restent peu nombreuses — au-delà, ce n'est plus un contrôle");
bilan();
