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
  const presents = POC.filter(k => A[k] !== undefined && !(k === "Traces" && A[k]._neutre));   // le proxy neutre est du produit
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

  console.log("— mode produit contre une API simulée par fetch : lire, ouvrir, patcher ————");
  {
    const M = [
      { id: "a1", sujet: "Devis 12", from_nom: "Jean", from_adresse: "jean@x.fr", date_recue: "2026-09-04T09:12:00+00:00", thread_id: "a1", nb_pieces_jointes: 0, taille: 1200, sens: "in", nature: "humain", snippet: "Bonjour", boite: "contact@exemple.fr", lu: false, statut: "nouveau", sorti_le: null, motif_sortie: null, dossier_origine: "inbox", dossier: null, tags: [], connu: false, usurpation: false, valide: false, suppr: false, reponse_possible: "oui", list_id: null, destinataires: [], reference: null, composition: null, fiabilite: null, contact_alternatif: null, dsn: null, dom: null },
      { id: "a2", sujet: "Re: Devis 12", from_nom: "Contact", from_adresse: "contact@exemple.fr", date_recue: "2026-09-04T11:00:00+00:00", thread_id: "a1", nb_pieces_jointes: 1, taille: 5000, sens: "out", nature: "humain", snippet: "Parfait", boite: "contact@exemple.fr", lu: true, statut: "nouveau", sorti_le: null, motif_sortie: null, dossier_origine: "sent", dossier: null, tags: [], connu: false, usurpation: false, valide: false, suppr: false, reponse_possible: "oui", list_id: null, destinataires: ["jean@x.fr"], reference: null, composition: null, fiabilite: null, contact_alternatif: null, dsn: null, dom: null },
    ];
    const appels = [];
    const rep = (o, status) => ({ status: status || 200, ok: (status || 200) < 400, json: () => Promise.resolve(o) });
    const api = (url, init) => {
      const m = (init && init.method) || "GET"; const u = url.replace(/^\/api\/v1/, ""); appels.push(m + " " + u.split("?")[0]);
      if (u === "/referentiels") return rep({ moi: { nom: "Test", login: "test", boites: [{ id: "b", adresse: "contact@exemple.fr", label: "contact" }] },
        speciaux: [{ id: "inbox", label: "Boîte de réception", icon: "📥" }, { id: "sent", label: "Envoyés", icon: "📤", sortant: true }], util: [], axes: [], valeurs: {}, statuts: [{ id: "nouveau", label: "Nouveau" }, { id: "traite", label: "Traité" }], vues: ["trash", "archives", "traites"], virtuels: [] });
      if (u === "/arborescence") return rep({ compteurs: { inbox: { t: 1, u: 1, f: 0 }, sent: { t: 1, u: 0, f: 0 } }, virtuels: [], epingles: [] });
      if (u.startsWith("/messages?")) return rep({ messages: M.filter(x => x.dossier_origine === (u.includes("dossier=sent") ? "sent" : "inbox")), total: 1 });
      let r = u.match(/^\/messages\/([^/?]+)\/fil$/); if (r) return rep({ messages: M.filter(x => x.thread_id === "a1") });
      r = u.match(/^\/messages\/([^/?]+)\/rattachement$/); if (r && m === "PATCH") { const x = M.find(y => y.id === r[1]); Object.assign(x, JSON.parse(init.body)); return rep({ ok: true, modifies: 1, message: x }); }
      r = u.match(/^\/messages\/([^/?]+)$/); if (r) { const x = M.find(y => y.id === r[1]); return x ? rep(Object.assign({ corps: "Bonjour, le devis.", pieces_jointes: [] }, x)) : rep({ message: "inconnu" }, 404); }
      return rep({ message: "route inconnue " + m + " " + u }, 404);
    };
    const q = demarrer(creerStockage(), { session: "api", fetch: (url, init) => Promise.resolve(api(url, init)) }); await drainer(q);
    const B = q.ABX;
    vrai(q.doc.getElementById("list").innerHTML.includes("Devis 12"), "la liste du vrai contrat se peint (dates ISO normalisées)");
    vrai(q.doc.getElementById("nav").innerHTML.includes("Boîte de réception"), "l'arborescence aussi");
    B.Controllers.Tabs.ouvrir({ type: "msg", id: "a1" });
    for (let i = 0; i < 6; i++) await drainer(q);
    const det = q.doc.getElementById("detail").innerHTML;
    vrai(det.includes("Devis 12") && det.includes("le devis"), "un message s'ouvre et son corps est là — sans ABX.Traces ni fixtures");
    const fils = appels.filter(a => a.endsWith("/fil")).length;
    eq(fils, 1, "le fil n'est chargé qu'UNE fois (" + fils + ") : le cache fusionne, il ne remplace pas");
    await B.MessageService.lire(B.Api.cache.message("a1"), true); await drainer(q);
    vrai(appels.some(a => a.startsWith("PATCH /messages/a1/rattachement")) && B.Api.cache.message("a1").lu === true, "marquer lu passe par PATCH et le cache suit");
    vrai(B.Traces && B.Traces._neutre, "ABX.Traces est le proxy neutre du produit");
  }

  console.log("— dette de migration : les vues lisent encore l'objet interne ————");
  const lister = d => fs.readdirSync(path.join(RACINE, d), { withFileTypes: true }).flatMap(e =>
    e.isDirectory() ? lister(path.join(d, e.name)) : [path.join(d, e.name)]);
  const srcJs = ["src/noyau", "src/modules"].flatMap(lister);
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
