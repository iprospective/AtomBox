/* LE MODE PRODUIT (D141, D142) — la preuve que la frontière est réelle.

   index.prod.html charge les mêmes vues, contrôleurs et registre que le POC,
   SANS les fichiers de la liste fermée. Ce test le charge sans réseau (fetch
   rejette) et vérifie : que ça tourne, que rien du POC n'y est, que l'interface
   TIENT avec une API indisponible, qu'aucun identifiant du CDC n'apparaît, et
   que chaque point de contexte expliqué par le CDC en POC a son explication
   pour l'utilisateur en prod — sinon l'utilisateur final aurait MOINS d'aide
   que le lecteur du POC. */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const { demarrer, drainer, creerStockage, eq, vrai, bilan, RACINE } = require("./run");
const { creerDocument } = require("./fake-dom");

(async () => {
  console.log("— mode produit : index.prod.html, sans réseau ————————————");
  const poc = demarrer(creerStockage()); await drainer(poc);
  process.env.ABX_INDEX = "index.prod.html";
  const p = demarrer(creerStockage());
  const A = p.ABX;
  let rejet = null;
  await drainer(p).catch(e => { rejet = e; });
  vrai(!rejet, "l'amorçage ne rejette pas — une API indisponible n'est pas une exception" + (rejet ? " : " + String(rejet.message).slice(0, 80) : ""));

  const POC = ["Corpus", "Fixtures", "PRNG", "QueryLog", "CDC", "ServeurSimule", "Traces", "Markdown", "ContexteCdc"];
  const presents = POC.filter(k => A[k] !== undefined);
  eq(presents.length, 0, "rien du POC n'est chargé" + (presents.length ? " — présents : " + presents.join(", ") : ""));
  vrai(A.Api && A.Api.branchee() && A.ApiHttp, "la couche d'accès est branchée sur l'implémentation HTTP");
  eq(A.Registry.modes.join(","), "aide", "un seul mode de contexte : « aide »");
  vrai(typeof A.log === "function", "ABX.log existe sans journal des requêtes");

  const nav = p.doc.getElementById("nav").innerHTML, list = p.doc.getElementById("list").innerHTML;
  vrai(nav.includes("navsearch") || nav.includes("Boîte de réception") || nav.length > 50, "l'arborescence est peinte (vide ou non)");
  vrai(list.includes("indisponible"), "la liste dit que le service est indisponible, au lieu de casser");
  const dom = nav + list + p.doc.getElementById("detail").innerHTML;
  vrai(!/\b[DQC]\d{3}b?\b/.test(dom), "aucun identifiant du CDC dans le DOM produit");

  const cdc = poc.ABX.Registry.pointsDuMode("cdc"), aide = A.Registry.pointsDuMode("aide");
  const sansAide = cdc.filter(pt => !aide.includes(pt));
  eq(sansAide.length, 0, cdc.length + " points de contexte du CDC ont tous leur explication utilisateur" +
     (sansAide.length ? " — manquent : " + sansAide.join(", ") : ""));
  const sansCdc = aide.filter(pt => !cdc.includes(pt));
  vrai(sansCdc.length === 0, "et réciproquement, chaque point d'aide est expliqué par le CDC en POC" +
     (sansCdc.length ? " — sans CDC : " + sansCdc.join(", ") : ""));

  console.log("— dette de migration : les vues lisent encore l'objet interne ————");
  const srcJs = ["js/controllers", "js/views", "js/services"].flatMap(d =>
    fs.readdirSync(path.join(RACINE, d)).map(f => path.join(d, f)));
  const deballages = srcJs.filter(f => !/serveur\.poc|api\.http/.test(f))
    .map(f => [f, (fs.readFileSync(path.join(RACINE, f), "utf8").match(/_m \|\| r|\._m\b/g) || []).length])
    .filter(([, n]) => n > 0);
  const total = deballages.reduce((s, [, n]) => s + n, 0);
  console.log("  déballages _m hors serveur simulé : " + total + " (" + deballages.map(([f, n]) => f.replace("js/", "") + "×" + n).join(", ") + ")");
  vrai(total <= 4, "la dette _m est bornée (" + total + " ≤ 4) — elle ne doit que baisser");

  console.log("— bundle produit ————————————————————————————————");
  const BUNDLE = path.join(RACINE, "dist", "prod.html");
  vrai(fs.existsSync(BUNDLE), "dist/prod.html existe");
  if (fs.existsSync(BUNDLE)) {
    const html = fs.readFileSync(BUNDLE, "utf8");
    const marques = [...html.matchAll(/\/\* ===== (js\/[^ ]+) ===== \*\//g)].map(m => m[1]);
    const interdits = marques.filter(f => /serveur\.poc|cdc-index|fixtures|corpus\.js|query-log|pages\.js|api-trace|markdown|contexte\.cdc|prng/.test(f));
    eq(interdits.length, 0, "le bundle produit n'embarque aucun fichier du POC" + (interdits.length ? " — " + interdits.join(", ") : ""));
    vrai(html.length < 400 * 1024, "le bundle produit est léger : " + Math.round(html.length / 1024) + " Ko");
  }
  bilan();
})().catch(e => { console.error("  ✗ échec du test produit :", e.stack.split("\n").slice(0, 3).join(" | ")); process.exit(1); });
