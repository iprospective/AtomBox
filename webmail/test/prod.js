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
  w.doc.getElementById("c_user").value = "camille"; w.doc.getElementById("c_pass").value = "secret";
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

  console.log("— envoyer en prod : c'est le SERVEUR qui nomme ————————————");
  /* Le serveur simulé du POC acceptait l'identifiant fabriqué par le client ; le vrai
     serveur donne le sien (UUID). En le jetant, l'onglet ouvert après l'envoi pointait
     sur un message que le serveur n'avait jamais eu — « ça part, mais rien ne change ». */
  {
    const vus = [];
    const rep = o => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(o) });
    const faux = (url, init) => {
      const m = (init && init.method) || "GET", chemin = url.replace("/api/v1", "");
      vus.push(m + " " + chemin.split("?")[0]);
      if (m === "POST" && chemin === "/messages") {
        const envoye = JSON.parse(init.body);
        vrai(envoye.cc !== undefined, "le Cc part au serveur — sinon un brouillon repris perd ses copies");
        return rep({ ok: true, crees: 1, message: Object.assign({}, envoye, { id: "srv-4242" }) });
      }
      if (chemin.startsWith("/messages/srv-4242")) return rep(Object.assign({ id: "srv-4242", sujet: "Essai" }));
      if (chemin.startsWith("/messages/br-1")) return rep({ id: "br-1", sujet: "À finir", dossier_origine: "drafts",
        destinataires: ["jean@exemple.fr"], corps: "début",
        composition: { mode: "new", src: null, de: "moi@exemple.fr", a: "jean@exemple.fr", cc: "paul@exemple.fr",
                       sujet: "À finir", corps: "début", pieces_jointes: [], reference: false } });
      if (chemin.startsWith("/messages")) return rep({ messages: [], total: 0 });
      if (chemin.startsWith("/arborescence")) return rep({ compteurs: {}, util: [], speciaux: [] });
      if (chemin.startsWith("/referentiels")) return rep({ moi: { nom: "x", boites: [{ adresse: "moi@exemple.fr" }] }, speciaux: [], util: [], axes: [] });
      return rep({ ok: true });
    };
    const e = demarrer(creerStockage(), { session: "api", fetch: faux });
    await drainer(e);
    const C = e.ABX.Controllers.Compose;
    C.demarrer("new", null);
    const t0 = e.ABX.Store.ui.tabs.find(x => x.type === "compo");
    vrai(!!t0, "l'onglet de composition est ouvert");
    Object.assign(t0.data, { a: "jean@exemple.fr", cc: "paul@exemple.fr", sujet: "Essai", corps: "texte" });
    await C.finir(t0, true);
    const ouvert = e.ABX.Store.ui.tabs.find(x => x.type === "msg");
    vrai(!!ouvert, "un onglet de message s'ouvre après l'envoi");
    eq(ouvert && ouvert.id, "srv-4242", "et il porte l'identifiant DU SERVEUR, pas celui fabriqué ici");
    vrai(!e.ABX.Store.ui.tabs.some(x => x.key === t0.key), "l'onglet de composition est refermé");

    /* La LISTE ne porte pas la composition (une seule passe, D078) : c'est le DÉTAIL qui la
       rapporte. Sans ce détour, un brouillon s'ouvrait en lecture et ne se reprenait plus. */
    const br = await e.ABX.Api.message("br-1");
    vrai(br && br.composition, "le détail d'un brouillon rapporte sa composition");
    e.ABX.Controllers.Compose.rouvrir(br);
    const repris = e.ABX.Store.ui.tabs.find(x => x.type === "compo");
    vrai(!!repris && repris.brouillon === "br-1", "il se rouvre en composition, sur le même brouillon");
    eq(repris && repris.data.cc, "paul@exemple.fr", "avec ses copies — le Cc a survécu à l'aller-retour");
  }

  console.log("— se connecter là où il n'y a pas d'API ————————————————");
  /* Une page statique servie sans serveur (le miroir public) répond 404 sur /session. Le client
     traduisait ça en « identifiants refusés » — il accusait l'utilisateur de ce dont il n'était
     pas responsable, et on cherchait un mot de passe pendant que le problème était l'adresse. */
  {
    const r404 = () => Promise.resolve({ ok: false, status: 404, json: () => Promise.resolve(null) });
    const s = demarrer(creerStockage(), { session: null, fetch: r404 });
    await drainer(s);
    s.doc.getElementById("c_user").value = "mathieu"; s.doc.getElementById("c_pass").value = "peu importe";
    await s.ABX.Controllers.Connexion.soumettre();
    const html = s.doc.getElementById("connexion").innerHTML;
    vrai(/maquette/.test(html) && /poc \/ poc/.test(html),
         "404 sur /session : l'écran dit qu'il n'y a pas de service ici, et quoi faire à la place");
    vrai(!/[Ii]dentifiants refusés/.test(html), "et surtout : il n'accuse pas les identifiants");

    const r401 = () => Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve(null) });
    const s2 = demarrer(creerStockage(), { session: null, fetch: r401 });
    await drainer(s2);
    s2.doc.getElementById("c_user").value = "mathieu"; s2.doc.getElementById("c_pass").value = "faux";
    await s2.ABX.Controllers.Connexion.soumettre();
    vrai(/[Ii]dentifiants refusés/.test(s2.doc.getElementById("connexion").innerHTML),
         "401, en revanche, dit bien que les identifiants sont refusés");
  }

  console.log("— mot de passe oublié : trois écrans, une réponse constante (F129) ————");
  {
    const vus = [];
    const rep = o => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(o) });
    const faux = (url, init) => {
      const m = (init && init.method) || "GET", chemin = url.replace("/api/v1", "").split("?")[0];
      vus.push(m + " " + chemin);
      if (m === "POST" && chemin === "/session/reinitialisation")
        return rep({ ok: true, message: "Si un compte correspond et qu'une adresse de secours y est enregistrée, un lien vient d'y être envoyé." });
      if (m === "PUT" && chemin === "/session/reinitialisation") {
        const c = JSON.parse(init.body);
        vrai(c.jeton === "JETON-123", "le jeton vient du fragment d'URL, pas d'un champ");
        return rep({ ok: true, message: "mot de passe changé" });
      }
      return rep({ ok: true });
    };
    const d = demarrer(creerStockage(), { session: null, fetch: faux });
    await drainer(d);
    const C = d.ABX.Controllers.Connexion;
    C.peindre({});
    vrai(/Mot de passe oublié/.test(d.doc.getElementById("connexion").innerHTML), "la porte propose « mot de passe oublié »");
    C.peindre({ page: "oubli" });
    d.doc.getElementById("o_user").value = "mathieu";
    await C.demander();
    const h = d.doc.getElementById("connexion").innerHTML;
    vrai(/Si un compte correspond/.test(h), "la réponse du serveur est affichée telle quelle — constante (D164)");
    vrai(!/introuvable|inconnu|n'existe/.test(h), "et elle ne dit jamais si le compte existe");

    // le lien reçu par mail : le jeton est dans le FRAGMENT, que le navigateur n'envoie pas au serveur
    const e = demarrer(creerStockage(), { session: null, fetch: faux, hash: "#reinitialiser=JETON-123" });
    await drainer(e);
    const C2 = e.ABX.Controllers.Connexion;
    C2.peindre({});
    vrai(/Nouveau mot de passe/.test(e.doc.getElementById("connexion").innerHTML),
         "un jeton dans le fragment ouvre directement le choix du nouveau mot de passe");
    vrai(/toutes les sessions ouvertes de ce compte seront fermées/.test(e.doc.getElementById("connexion").innerHTML.replace(/\s+/g, " ")),
         "et l'écran dit ce que ça va faire : toutes les sessions tombent");
    e.doc.getElementById("r_pass").value = "trop-court"; e.doc.getElementById("r_pass2").value = "different";
    await C2.reinitialiser();
    vrai(/diffèrent/.test(e.doc.getElementById("connexion").innerHTML), "deux saisies qui diffèrent sont refusées avant le réseau");
    e.doc.getElementById("r_pass").value = "un-mot-de-passe-neuf"; e.doc.getElementById("r_pass2").value = "un-mot-de-passe-neuf";
    await C2.reinitialiser();
    vrai(/Mot de passe changé/.test(e.doc.getElementById("connexion").innerHTML), "puis l'écran renvoie à la connexion");
    vrai(vus.includes("PUT /session/reinitialisation"), "le PUT a bien été fait");
  }

  console.log("— en produit, CHAQUE écran s'ouvre vraiment (RM3176) ————————");
  /* Les deux bugs trouvés à l'usage — administration vide, « mes dossiers + » inerte — avaient la
     même cause : du code de maquette exécuté en produit. Le harnais n'ouvrait aucun de ces écrans.
     Il les ouvre tous maintenant, et vérifie qu'ils PEIGNENT quelque chose. */
  {
    const rep = o => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(o) });
    const faux = (url, init) => {
      const chemin = url.replace("/api/v1", "").split("?")[0];
      if (chemin === "/referentiels") return rep({ moi: { nom: "x", login: "x", boites: [{ id: "b", adresse: "moi@exemple.fr", label: "moi" }] },
        speciaux: [{ id: "inbox", label: "Boîte de réception", icon: "📥" }], util: [],
        axes: [{ id: "client", label: "Client" }], valeurs: { client: [{ id: "Tessier", label: "Tessier" }] },
        statuts: [], vues: [], virtuels: [] });
      if (chemin === "/arborescence") return rep({ compteurs: {}, virtuels: [], epingles: [] });
      if (chemin === "/etat") return rep({ ingestion: [], files: {}, magasin: {}, contenu: {}, regles: [] });
      if (chemin === "/journal") return rep({ lignes: [] });
      if (chemin === "/filtres") return rep({ filtres: [], total: 0, champs: [], operateurs: [], actions: [] });
      if (chemin === "/messages") return rep({ messages: [], total: 0 });
      return rep({ ok: true });
    };
    const e = demarrer(creerStockage(), { session: "api", fetch: faux });
    await drainer(e);
    const A2 = e.ABX, doc = e.doc;

    /* l'administration : elle ne doit proposer que ce qu'un serveur sert, et PEINDRE */
    A2.Controllers.Tabs.ouvrir({ type: "admin", volet: null }, false);
    await drainer(e).catch(() => {});
    const adm = doc.getElementById("detail").innerHTML;
    vrai(adm.length > 200, "l'administration peint quelque chose (" + adm.length + " caractères)");
    vrai(/État & journal|Règles/.test(adm), "et propose les volets qui ont un serveur derrière");
    vrai(!/Domaines & boîtes|Suite collaborative/.test(adm),
         "sans proposer les volets qui n'existent qu'en maquette");

    /* « mes dossiers + » : le clic doit ouvrir le formulaire, même sans axe servi */
    const nav = A2.Controllers.Nav;
    A2.Store.ui.formVirtuel = null;
    nav.peindre();
    const plus = doc.getElementById("v_new");
    vrai(!!plus, "le bouton + de « mes dossiers » est là");
    plus.onclick({ preventDefault() {}, stopPropagation() {} });
    vrai(!!A2.Store.ui.formVirtuel, "le clic ouvre le formulaire — il levait sur axes[0] et mourait en silence");
    eq(A2.Store.ui.formVirtuel.criteres[0].axe, "client", "et le premier axe SERVI est proposé");

    /* le même clic quand le serveur ne sert AUCUN axe : il ne doit pas casser */
    A2.Ref.axes = [];
    A2.Store.ui.formVirtuel = null;
    nav.peindre();
    doc.getElementById("v_new").onclick({ preventDefault() {}, stopPropagation() {} });
    vrai(!!A2.Store.ui.formVirtuel, "sans aucun axe, le formulaire s'ouvre quand même");
  }

  console.log("— les filtres de la liste REDEMANDENT au serveur ————————");
  /* Ils repeignaient depuis le cache : la puce changeait d'état, la liste restait identique.
     Le test ne regarde donc pas l'écran mais la REQUÊTE — c'est elle qui porte le filtre. */
  {
    const vus = [];
    const rep = o => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(o) });
    const faux = (url, init) => {
      const chemin = url.replace("/api/v1", "");
      if (chemin.startsWith("/messages?")) { vus.push(chemin); return rep({ messages: [], total: 0 }); }
      if (chemin.startsWith("/referentiels")) return rep({ moi: { nom: "x", login: "x", boites: [] },
        speciaux: [{ id: "inbox", label: "Boîte de réception", icon: "📥" }], util: [], axes: [], valeurs: {},
        statuts: [], vues: [], virtuels: [] });
      if (chemin.startsWith("/arborescence")) return rep({ compteurs: {}, virtuels: [], epingles: [] });
      return rep({ ok: true });
    };
    const e = demarrer(creerStockage(), { session: "api", fetch: faux });
    await drainer(e);
    const L = e.ABX.Controllers.List;
    L.ouvrir({ id: "inbox", label: "Boîte de réception", kind: "special" });
    await drainer(e);
    const avant = vus.length;

    const puce = { dataset: { f: "non_lus" } };
    e.ABX.Store.ui.filtre = "non_lus"; await L.charger();
    vrai(vus.length > avant, "changer de filtre déclenche une requête");
    vrai(/filtre=non_lus/.test(vus[vus.length - 1]), "et le filtre voyage DANS la requête : " + vus[vus.length - 1]);

    e.ABX.Store.ui.sens = "out"; await L.charger();
    vrai(/sens=out/.test(vus[vus.length - 1]), "le sens aussi");
    e.ABX.Store.ui.tri = "taille"; await L.charger();
    vrai(/tri=taille/.test(vus[vus.length - 1]), "le tri aussi — il ne se fait pas dans le navigateur (D078)");

    /* et le câblage lui-même : le clic doit appeler charger, pas peindre */
    const src = require("fs").readFileSync(RACINE + "/src/modules/liste/controleur.js", "utf8");
    const bloc_f = src.slice(src.indexOf('data-f]'), src.indexOf('data-f]') + 220);
    vrai(/List\.charger\(\)/.test(bloc_f) && !/List\.peindre\(\);\s*List\.logFiltre/.test(bloc_f),
         "le clic sur un filtre appelle charger(), pas peindre()");
  }

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
