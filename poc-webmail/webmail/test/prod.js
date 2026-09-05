/* LE MODE PRODUIT (D141, D142, D157) — la preuve que la frontière est réelle.

   Il n'y a qu'un index : la maquette est une session (poc/poc). Ce test ouvre la
   MÊME page avec une session « api », sans réseau (fetch rejette), et vérifie : que ça tourne, que rien du POC n'y est, que l'interface
   TIENT avec une API indisponible, qu'aucun identifiant du CDC n'apparaît, et
   que chaque point de contexte expliqué par le CDC en POC a son explication
   pour l'utilisateur en prod — sinon l'utilisateur final aurait MOINS d'aide
   que le lecteur du POC. */
"use strict";
const fs = require("fs"), path = require("path"), vm = require("vm");
const { demarrer, drainer, creerStockage, eq, vrai, bilan, RACINE } = require("./run");
const { creerDocument } = require("./fake-dom");

(async () => {
  console.log("— mode produit : le même index, session « api », sans réseau ————————————");
  const poc = demarrer(creerStockage()); await drainer(poc);
  const p = demarrer(creerStockage(), { session: "api" });
  const A = p.ABX;
  let rejet = null;
  await drainer(p).catch(e => { rejet = e; });
  vrai(!rejet, "l'amorçage ne rejette pas — une API indisponible n'est pas une exception" + (rejet ? " : " + String(rejet.message).slice(0, 80) : ""));

  const POC = ["Corpus", "Fixtures", "PRNG", "QueryLog", "CDC", "ServeurSimule", "Traces", "Markdown", "ContexteCdc", "PocBar"];
  const presents = POC.filter(k => A[k] !== undefined);
  eq(presents.length, 0, "rien du POC n'est chargé" + (presents.length ? " — présents : " + presents.join(", ") : ""));
  vrai(p.fichiers.every(f => !/prng|markdown|query-log|cdc-index|fixtures|corpus|contexte\.cdc|pages|api-trace|serveur\.poc|pocbar/.test(f)),
       "le chargeur n'a écrit aucun fichier du POC : " + p.fichiers.length + " scripts, ceux de l'index");
  vrai(poc.fichiers.length > p.fichiers.length, "la session poc en charge davantage (" + poc.fichiers.length + ") — la liste fermée, à ses trois points");
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

  console.log("— sans session : l'écran de connexion, et rien d'autre ————");
  const v = demarrer(creerStockage(), { session: null }); await drainer(v);
  const hc = v.doc.getElementById("connexion").innerHTML;
  vrai(hc.includes("c_user") && hc.includes("c_pass"), "l'écran de connexion est peint");
  eq(v.doc.getElementById("nav").innerHTML, "", "l'arborescence n'est pas peinte");
  vrai(v.ABX.Corpus === undefined, "et rien du POC n'est chargé avant la porte");
  vrai(!/\b[DQC]\d{3}b?\b/.test(hc) && !hc.includes("poc/poc"), "la porte ne dit ni un identifiant du CDC ni poc/poc");
  v.doc.getElementById("c_user").value = "poc"; v.doc.getElementById("c_pass").value = "poc";
  await v.ABX.Controllers.Connexion.soumettre();
  eq(JSON.parse(v.ls.getItem("abx.session")).mode, "poc", "poc/poc ouvre une session simulée (D157)");
  const v2 = demarrer(v.ls); await drainer(v2);
  vrai(!!v2.ABX.Corpus && !!v2.ABX.ServeurSimule && v2.ABX.PocBar && v2.ABX.PocBar.chargee, "au rechargement, le chargeur écrit le POC — corpus, serveur simulé, barre");
  vrai(v2.doc.getElementById("list").innerHTML.includes("msg"), "et la maquette est là");
  v2.ABX.Session.fermer();
  const v3 = demarrer(v.ls, { session: null }); await drainer(v3);
  vrai(v3.ABX.Corpus === undefined && v3.doc.getElementById("connexion").innerHTML.includes("c_user"), "se déconnecter ramène à la porte, sans rien du POC");
  const w = demarrer(creerStockage(), { session: null }); await drainer(w);
  w.doc.getElementById("c_user").value = "mathieu"; w.doc.getElementById("c_pass").value = "secret";
  await w.ABX.Controllers.Connexion.soumettre();
  vrai(w.ls.getItem("abx.session") === null && w.doc.getElementById("connexion").innerHTML.includes("indisponible"),
       "d'autres identifiants vont au serveur — indisponible ici, la porte le dit et ne s'ouvre pas");

  console.log("— dette de migration : les vues lisent encore l'objet interne ————");
  const srcJs = ["js/controllers", "js/views", "js/services"].flatMap(d =>
    fs.readdirSync(path.join(RACINE, d)).map(f => path.join(d, f)));
  const deballages = srcJs.filter(f => !/serveur\.poc|api\.http/.test(f))
    .map(f => [f, (fs.readFileSync(path.join(RACINE, f), "utf8").match(/_m \|\| r|\._m\b/g) || []).length])
    .filter(([, n]) => n > 0);
  const total = deballages.reduce((s, [, n]) => s + n, 0);
  console.log("  déballages _m hors serveur simulé : " + total + " (" + deballages.map(([f, n]) => f.replace("js/", "") + "×" + n).join(", ") + ")");
  eq(total, 0, "la dette _m est SOLDÉE : les vues lisent le contrat, aucun déballage (" + total + ")");

  console.log("— bundle produit ————————————————————————————————");
  const BUNDLE = path.join(RACINE, "dist", "prod.html");
  vrai(fs.existsSync(BUNDLE), "dist/prod.html existe");
  if (fs.existsSync(BUNDLE)) {
    const html = fs.readFileSync(BUNDLE, "utf8");
    const marques = [...html.matchAll(/\/\* ===== (js\/[^ ]+) ===== \*\//g)].map(m => m[1]);
    const interdits = marques.filter(f => /serveur\.poc|cdc-index|fixtures|corpus\.js|query-log|pages\.js|api-trace|markdown|contexte\.cdc|prng|pocbar/.test(f));
    vrai(html.includes("window.ABX_SANS_POC = true"), "le bundle produit refuse poc/poc (ABX_SANS_POC)");
    eq(interdits.length, 0, "le bundle produit n'embarque aucun fichier du POC" + (interdits.length ? " — " + interdits.join(", ") : ""));
    vrai(html.length < 400 * 1024, "le bundle produit est léger : " + Math.round(html.length / 1024) + " Ko");
  }
  bilan();
})().catch(e => { console.error("  ✗ échec du test produit :", e.stack.split("\n").slice(0, 3).join(" | ")); process.exit(1); });
