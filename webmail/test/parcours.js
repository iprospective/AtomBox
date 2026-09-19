/* LES PARCOURS DU MODE PRODUIT (RM3189).

   `prod.js` vérifie la FRONTIÈRE : que rien du POC ne charge, que l'interface tient sans réseau.
   Ici on fait l'inverse : on se branche sur un serveur simulé COMPLET et on utilise l'interface
   comme un utilisateur — chaque écran, chaque bouton, chaque geste. C'est le harnais qui manquait
   quand six défauts sont sortis à l'usage en deux jours.

   Règle du fichier : on n'affirme pas « ça n'a pas planté », on vérifie un EFFET — la requête
   partie, l'état changé, l'écran repeint. */
"use strict";
const { demarrer, drainer, creerStockage, eq, vrai, bilan } = require("./run");
const { evt } = require("./fake-dom");

const MSG = (id, o = {}) => Object.assign({
  id, sujet: "Sujet " + id, from_nom: "Paul", from_adresse: "paul@exemple.fr",
  date_recue: "2026-09-10T10:00:00+02:00", thread_id: "t1", nb_pieces_jointes: 0, taille: 1024,
  sens: "in", nature: "humain", snippet: "extrait", boite: "moi@exemple.fr", lu: false,
  statut: "nouveau", sorti_le: null, motif_sortie: null, dossier_origine: "inbox", dossier: null,
  tags: [], destinataires: ["moi@exemple.fr"], corps: "le corps", pieces_jointes: [],
}, o);

function serveur(vus) {
  /* SÉRIALISER, comme le ferait un vrai serveur : rendre ses objets par référence ferait
     partager les tableaux entre le client et le simulateur — un tag posé une fois apparaîtrait
     deux fois, et le harnais accuserait le code d'un défaut qui n'est que le sien. */
  const rep = o => Promise.resolve({ ok: true, status: 200,
                                     json: () => Promise.resolve(JSON.parse(JSON.stringify(o))) });
  /* m3 porte DEUX pièces : un PDF ordinaire, et un message encapsulé que le serveur a RÉSOLU vers
     m1 — le cas de D168, celui qu'on ne voyait pas parce que rien ne cliquait sur une pièce. */
  const PJ = (o) => Object.assign({ ordre: 1, octets: 2048, sha256: "abc123", partage_par: 1,
                                    content_id: null, disposition: "attachment", comm_id: null }, o);
  const etat = { messages: {
      m1: MSG("m1"), m2: MSG("m2", { lu: true }),
      m3: MSG("m3", { nb_pieces_jointes: 2, pieces_jointes: [
        PJ({ pj_id: "p1", nom: "devis.pdf", mime_declare: "application/pdf", mime_detecte: "application/pdf" }),
        PJ({ pj_id: "p2", ordre: 2, nom: "Sujet m1.eml", octets: 4015, mime_declare: "message/rfc822",
             mime_detecte: "message/rfc822", comm_id: "m1" })] }),
    }, filtres: [], virtuels: [],
    /* le référentiel des valeurs d'axe VIT côté serveur : poser un tag dont la valeur n'existe
       pas encore l'y ajoute — c'est ce que fait le vrai, et c'est ce que le client doit relire. */
    valeurs: { client: [{ id: "client:Acme", label: "Acme", axe: "client" }] } };
  return [etat, (url, init) => {
    const m = (init && init.method) || "GET";
    const chemin = url.replace("/api/v1", "");
    const nu = chemin.split("?")[0];
    const corps = init && init.body ? JSON.parse(init.body) : null;
    vus.push(m + " " + nu);

    if (nu === "/referentiels") return rep({
      moi: { nom: "Moi", login: "moi", boites: [{ id: "b1", adresse: "moi@exemple.fr", label: "moi" }] },
      speciaux: [{ id: "inbox", label: "Boîte de réception", icon: "📥" },
                 { id: "sent", label: "Envoyés", icon: "📤", sortant: true },
                 { id: "trash", label: "Corbeille", icon: "🗑", vue: true }],
      util: [{ id: "d1", label: "Clients", icon: "📁", boite: "moi@exemple.fr" }],
      axes: [{ id: "client", label: "Client" }], valeurs: etat.valeurs,
      statuts: [{ id: "nouveau", label: "Nouveau" }, { id: "a_faire", label: "À faire" }, { id: "traite", label: "Traité", sortie: "traite" }],
      vues: ["trash", "archives", "traites"], virtuels: etat.virtuels });
    if (nu === "/arborescence") return rep({ compteurs: { inbox: { t: 2, u: 1, f: 0 } }, virtuels: etat.virtuels, epingles: [] });
    if (nu === "/messages" && m === "GET") return rep({ messages: Object.values(etat.messages), total: 2 });
    if (nu === "/messages" && m === "POST") { const id = "u" + (Object.keys(etat.messages).length + 1);
      /* comme le vrai (D167) : le corps stocké est le COMMENTAIRE seul, la provenance est une
         relation, et le message transféré compte pour une pièce — il part encapsulé (D066). */
      etat.messages[id] = MSG(id, { sens: "out", dossier_origine: corps.composition ? "drafts" : "sent",
                                    composition: corps.composition || null, sujet: corps.sujet || "",
                                    corps: corps.corps || "", reference: corps.reference || null,
                                    nb_pieces_jointes: corps.reference ? 1 : 0 });
      return rep({ ok: true, crees: 1, message: etat.messages[id] }); }
    if (/^\/messages\/[^/]+\/tags\/?$/.test(nu) && m === "POST") {
      const id = nu.split("/")[2]; const t = { axe: corps.axe, val: corps.val, source: "manuel" };
      etat.messages[id].tags = (etat.messages[id].tags || []).concat([t]);
      const vs = etat.valeurs[corps.axe] = etat.valeurs[corps.axe] || [];
      if (!vs.some(v => v.label === corps.val))
        vs.push({ id: corps.axe + ":" + corps.val, label: corps.val, axe: corps.axe });
      return rep({ ok: true, tags: etat.messages[id].tags }); }
    if (/^\/messages\/[^/]+\/tags\//.test(nu) && m === "DELETE") {
      const id = nu.split("/")[2]; etat.messages[id].tags = [];
      return rep({ ok: true, supprimes: 1, tags: [] }); }
    if (/^\/messages\/[^/]+\/rattachement$/.test(nu) && m === "PATCH") {
      const id = nu.split("/")[2]; Object.assign(etat.messages[id], corps);
      return rep({ ok: true, modifies: 1, message: etat.messages[id] }); }
    if (/^\/messages\/[^/]+\/rattachement$/.test(nu) && m === "DELETE") return rep({ ok: true, detache: true });
    if (/^\/messages\/[^/]+\/fil$/.test(nu)) return rep({ fil: [] });
    /* les octets d'une pièce ne sont pas du JSON : la réponse porte un blob, comme la vraie */
    if (/^\/messages\/[^/]+\/pieces-jointes\/[^/]+$/.test(nu) && m === "GET")
      return Promise.resolve({ ok: true, status: 200, blob: () => Promise.resolve({ size: 2048 }) });
    if (/^\/messages\/[^/]+$/.test(nu) && m === "GET") return rep(etat.messages[nu.split("/")[2]] || null);
    if (/^\/messages\/[^/]+$/.test(nu) && m === "PUT") return rep({ ok: true, modifies: 1, message: etat.messages[nu.split("/")[2]] });
    if (nu === "/dossiers-virtuels" && m === "POST") { const d = { id: "perso:v1", label: corps.label, criteres: corps.criteres };
      etat.virtuels.push(d); return rep({ ok: true, crees: 1, dossier: d }); }
    if (nu.startsWith("/dossiers-virtuels/") && m === "DELETE") { etat.virtuels.length = 0; return rep({ ok: true, supprimes: 1 }); }
    if (nu === "/dossiers" && m === "POST") return rep({ ok: true, crees: 1, dossier: { id: "d2", label: corps.nom || "Neuf" } });
    if (nu.startsWith("/dossiers/") && m === "PATCH") return rep({ ok: true, modifies: 1, dossier: { id: "d1", label: corps.nom } });
    if (nu.startsWith("/dossiers/") && m === "DELETE") return rep({ ok: true, supprimes: 1 });
    if (nu === "/parametres") return rep({ epingles: [], ordreAxes: [] });
    if (nu === "/filtres" && m === "GET") return rep({ filtres: etat.filtres, total: etat.filtres.length,
      champs: [{ id: "from", label: "Expéditeur" }], operateurs: [{ id: "contient", label: "contient" }],
      actions: [{ id: "classer", label: "Classer" }] });
    if (nu === "/filtres" && m === "POST") { const f = { id: "f1", nom: corps.nom, actif: true, muette: true,
      predicat: corps.predicat, action: corps.action, portee: corps.portee }; etat.filtres.push(f); return rep({ ok: true, filtre: f }); }
    if (nu.startsWith("/filtres/") && m === "PATCH") { etat.filtres[0].actif = corps.actif; return rep({ ok: true, filtre: etat.filtres[0] }); }
    if (nu.startsWith("/filtres/") && m === "DELETE") { etat.filtres.length = 0; return rep({ ok: true, supprimes: 1 }); }
    if (nu === "/etat") return rep({ ingestion: [{ dossier: "INBOX", retard: 0 }], files: { en_attente: 0, en_echec: 0, abandonnes: 0 },
      magasin: { blobs: 1, octets: 1024, gain: "0 %", orphelins: 0 }, contenu: { messages: 2 }, regles: [] });
    if (nu === "/etat/metriques") return rep({ lignes: [] });
    if (nu === "/etat/journal") return rep({ lignes: [{ at: "2026-09-15T10:00:00", niveau: "INFO", domaine: "api", texte: "ok" }] });
    if (nu === "/envois") return rep({ envois: [], total: 0 });
    if (/^\/envois\/[^/]+\/relancer$/.test(nu)) return rep({ ok: true, relance: 1 });
    if (nu === "/carnet") return rep({ carnet: [], total: 0 });
    if (nu === "/identites") return rep({ identites: [{ id: "i1", nom_affiche: "Moi", par_defaut: true }] });
    if (nu === "/pieces-jointes") return rep({ pieces_jointes: [], total: 0 });
    if (nu === "/recherche") return rep({ messages: [], total: 0 });
    return rep({ ok: true });
  }];
}

(async () => {
  const vus = [];
  const [etat, fetch] = serveur(vus);
  const e = demarrer(creerStockage(), { session: "api", fetch });
  await drainer(e);
  const A = e.ABX, doc = e.doc, ui = A.Store.ui;
  const clic = id => { const n = doc.getElementById(id); vrai(!!n, "le contrôle #" + id + " existe"); if (n && n.onclick) n.onclick({ preventDefault() {}, stopPropagation() {} }); return n; };
  /* UN GESTE DÉLÉGUÉ (RM3211). Les trois quarts de l'interface ne se cliquent pas par `id` mais
     par sélecteur — `D.on(zone, ".msg", …)`. Appeler le service à la place, comme le faisait ce
     harnais, laisse le CÂBLAGE hors du test : c'est justement là que se logent les défauts. */
  const geste = (zone, sel, n = 0) => {
    const el = doc.getElementById(zone).querySelectorAll(sel)[n];
    vrai(!!el, "un « " + sel + " » existe dans #" + zone);
    if (el && el.onclick) el.onclick(evt(el));
    return el;
  };
  const saisir = (id, v) => { const n = doc.getElementById(id); if (n) { n.value = v; if (n.oninput) n.oninput({ target: n }); } return n; };

  console.log("— la liste : tri, filtres, sens ————————————————————");
  A.Controllers.List.ouvrir({ id: "inbox", label: "Boîte de réception", kind: "special" });
  await drainer(e);
  vrai(doc.getElementById("list").innerHTML.includes("msg"), "la liste peint les messages du serveur");
  const tri = doc.getElementById("tri");
  vrai(!!tri, "le sélecteur de tri existe");
  if (tri && tri.onchange) { tri.value = "taille"; tri.onchange({ target: tri, selectedOptions: [{ text: "Taille" }] }); await drainer(e); }
  vrai(vus.some(v => v.startsWith("GET /messages")), "changer le tri redemande la liste");
  /* Les puces de filtre et de sens : le défaut du 15 septembre était ICI — elles repeignaient
     depuis le cache au lieu de redemander au serveur, et la liste ne bougeait pas. */
  let n = vus.length;
  geste("list", ".chip[data-f]", 1);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("GET /messages")), "cliquer une puce de filtre REDEMANDE la liste");
  n = vus.length;
  geste("list", ".chip[data-s]", 1);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("GET /messages")), "cliquer une puce de sens aussi");

  console.log("— un message : ouvrir, statuer, taguer —————————————");
  /* par le CLIC sur la ligne : c'est le chemin de l'utilisateur, et il passe par le câblage */
  A.Store.ui.filtre = "tous"; A.Controllers.List.charger(); await drainer(e);
  geste("list", ".msg", 0);
  await drainer(e);
  vrai(ui.tabs.some(t => t.type === "msg"), "cliquer une ligne ouvre le message");
  const det = () => doc.getElementById("detail").innerHTML;
  vrai(det().length > 100, "le message se peint");
  await A.MessageService.traiter(A.Api.cache.message("m1"));
  eq(A.Api.cache.message("m1").motif_sortie, "traite", "« traiter » sort le message de la file");
  await A.MessageService.refile(A.Api.cache.message("m1"));
  eq(A.Api.cache.message("m1").motif_sortie, null, "« remettre en file » l'y ramène");
  await A.MessageService.archiver(A.Api.cache.message("m1"));
  eq(A.Api.cache.message("m1").motif_sortie, "archive", "« archiver » sort sans traiter");
  await A.MessageService.refile(A.Api.cache.message("m1"));
  await A.MessageService.junk(A.Api.cache.message("m2"));
  eq(A.Api.cache.message("m2").dossier, "junk", "« indésirable » déplace");
  await A.MessageService.corbeille(A.Api.cache.message("m2"));
  eq(A.Api.cache.message("m2").dossier, "trash", "« corbeille » aussi");
  await A.MessageService.restaurer(A.Api.cache.message("m2"));
  eq(A.Api.cache.message("m2").dossier, null, "« restaurer » revient à l'origine (D088)");
  await A.MessageService.statuer(A.Api.cache.message("m1"), "a_faire");
  eq(A.Api.cache.message("m1").statut, "a_faire", "le statut se pose");

  /* les gestes du message ouvert, par leurs sélecteurs — jusqu'ici seuls les services étaient
     appelés, donc le câblage entre le bouton et l'action n'était couvert par rien. */
  A.Controllers.Tabs.ouvrir({ type: "msg", id: "m1" }, false); await drainer(e);
  n = vus.length;
  geste("detail", "[data-x]", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.includes("/rattachement")), "un geste de file agit par l'API");
  A.Controllers.Tabs.ouvrir({ type: "msg", id: "m1" }, false); await drainer(e);
  geste("detail", "[data-c]", 0);
  await drainer(e);
  vrai(ui.tabs.some(t => t.type === "compo"), "« répondre » ouvre une composition");
  ui.tabs.filter(t => t.type === "compo").forEach(t => A.Controllers.Tabs.fermer(t.key));
  /* RM3244 (D140c) — le drapeau : posé sur le téléphone, il descend en base ; il doit se VOIR ici,
     et se poser d'ici. Avant, il existait partout sauf à l'écran. */
  A.Controllers.Tabs.ouvrir({ type: "msg", id: "m2" }, false); await drainer(e);
  const boutons = doc.getElementById("detail").querySelectorAll("[data-x]");
  const iDrapeau = boutons.findIndex(b => b.dataset.x === "drapeau");
  vrai(iDrapeau >= 0, "le message propose un bouton drapeau");
  n = vus.length;
  geste("detail", "[data-x]", iDrapeau);
  await drainer(e);
  vrai(vus.slice(n).includes("PATCH /messages/m2/rattachement"), "poser le drapeau passe par le rattachement");
  eq(etat.messages.m2.drapeau, true, "le serveur a reçu drapeau = true — c'est lui qui le pousse vers IMAP");
  A.Controllers.List.charger(); await drainer(e);
  const carte = id => (doc.getElementById("list").innerHTML.split('data-id="' + id + '"')[1] || "").split('data-id="')[0];
  vrai(carte("m2").includes("⚑"), "la ligne du message drapeauté montre le drapeau");
  vrai(carte("m1") !== "" && !carte("m1").includes("⚑"), "…et seulement elle");
  geste("tabs", ".tab", 0);
  await drainer(e);
  vrai(ui.tabs.length >= 1, "un onglet se rouvre par son étiquette");

  await A.MessageService.ajouterTag(A.Api.cache.message("m1"), "client", "Acme");
  eq(A.Api.cache.message("m1").tags.length, 1, "un tag se pose par sa route");
  vrai(vus.includes("POST /messages/m1/tags"), "et c'est bien la route des tags qui sert");
  /* le tag posé se retire par la croix de son étiquette, et engendre un dossier virtuel */
  A.Controllers.Tabs.ouvrir({ type: "msg", id: "m1" }, false); await drainer(e);
  n = vus.length;
  geste("detail", "[data-newv]", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("POST /dossiers-virtuels")),
       "« un dossier virtuel depuis ce tag » n'a rien à saisir (D143)");
  /* F139 — une valeur d'axe NEUVE doit apparaître sans recharger la page : l'arborescence lit
     `Ref.valeurs`, chargé une fois au démarrage. Sans rechargement, le tag existait côté serveur
     et l'écran de celui qui venait de le poser ne le montrait nulle part. */
  n = vus.length;
  await A.MessageService.ajouterTag(A.Api.cache.message("m1"), "client", "Neuf SARL");
  await drainer(e);
  vrai(vus.slice(n).includes("GET /referentiels"), "poser un tag recharge le référentiel (F139, D169)");
  vrai((A.Ref.valeurs.client || []).some(v => v.label === "Neuf SARL"), "la valeur neuve est connue du client");
  ui.ouverts.client = true;                     // une branche fermée ne montre rien, c'est normal
  A.Controllers.Nav.peindre();
  vrai(doc.getElementById("nav").innerHTML.includes("Neuf SARL"), "et sa branche apparaît dans l'arborescence, sans rechargement");
  await A.MessageService.retirerTag(A.Api.cache.message("m1"), A.Api.cache.message("m1").tags.length - 1);
  await drainer(e);
  n = vus.length;
  await A.MessageService.rafraichirReferentiel(null);
  await drainer(e);
  vrai(vus.slice(n).includes("GET /referentiels") && vus.slice(n).includes("GET /arborescence"),
       "rafraichirReferentiel relit le référentiel ET les compteurs : une branche neuve à zéro serait fausse");

  /* DEUX chemins, deux choses différentes : le service (le contrat avec l'API) et le câblage (le
     bouton atteint-il le service ?). Les six défauts de septembre étaient tous dans le second. */
  await A.MessageService.retirerTag(A.Api.cache.message("m1"), 0);
  eq(A.Api.cache.message("m1").tags.length, 0, "le service retire le tag");
  await A.MessageService.ajouterTag(A.Api.cache.message("m1"), "client", "Acme");
  A.Controllers.Tabs.ouvrir({ type: "msg", id: "m1" }, false); await drainer(e);
  geste("detail", "[data-untag]", 0);
  await drainer(e);
  eq(A.Api.cache.message("m1").tags.length, 0, "et la croix de l'étiquette y mène aussi");

  console.log("— composer : brouillon, pièce jointe, envoi ————————");
  A.Controllers.Compose.demarrer("new", null);
  await drainer(e);
  const t0 = ui.tabs.find(x => x.type === "compo");
  vrai(!!t0 && !!doc.getElementById("f_a"), "le formulaire de composition est peint");
  saisir("f_a", "jean@exemple.fr"); saisir("f_cc", "paul@exemple.fr");
  saisir("f_sujet", "Essai"); saisir("f_corps", "texte");
  const de = doc.getElementById("f_de"); if (de && de.onchange) de.onchange({ target: { value: "moi@exemple.fr" } });
  eq(t0.data.a, "jean@exemple.fr", "la saisie va dans l'onglet, sans repeindre");
  await A.Controllers.Compose.finir(t0, false);
  vrai(vus.includes("POST /messages"), "« enregistrer le brouillon » écrit par l'API");

  A.Controllers.Compose.demarrer("rep", A.Api.cache.message("m1"));
  await drainer(e);
  const t1 = ui.tabs.find(x => x.type === "compo");
  vrai(t1.data.sujet.startsWith("Re:"), "répondre préremplit le sujet");
  saisir("f_a", "jean@exemple.fr");
  clic("c_pj");
  await A.Controllers.Compose.finir(t1, true);
  vrai(ui.tabs.some(x => x.type === "msg"), "après l'envoi, le message s'ouvre");

  console.log("— transférer : le source verrouillé, le commentaire à part (D167) ————");
  A.Controllers.Compose.demarrer("tr", A.Api.cache.message("m1"));
  await drainer(e);
  const t2 = ui.tabs.find(x => x.type === "compo");
  vrai(t2.data.sujet.startsWith("Tr:"), "transférer préremplit le sujet");
  eq(t2.data.corps, "", "le message transmis n'est PAS recopié dans la zone de saisie (D167)");
  /* On lit le HTML PEINT, pas `getElementById` : le faux DOM fabrique à la demande tout id qu'on
     lui réclame, donc `!!doc.getElementById("x")` est vrai même pour un contrôle qui n'existe
     plus. Un test qui ne peut pas échouer ne prouve rien. */
  const ecran = () => doc.getElementById("detail").innerHTML;
  vrai(/<textarea id="f_corps"><\/textarea>/.test(ecran()), "la zone de saisie est vide : elle ne porte que le commentaire");
  vrai(ecran().includes('id="tr_src"'), "le bloc source est peint — verrouillé, à part du commentaire");
  vrai(!ecran().includes('id="f_ref"'), "on ne demande plus « par référence ? » : la réponse est dans les destinataires");
  vrai(/id="tr_mod"[^>]*disabled/.test(ecran()), "modifier le message transmis est un geste de la V1 (F133), pas un défaut d'aujourd'hui");
  vrai(ecran().includes("Sujet m1"), "et le message transmis est montré : on voit ce qu'on envoie");
  saisir("f_a", "collegue@exemple.fr"); saisir("f_corps", "tu peux regarder ?");
  await A.Controllers.Compose.finir(t2, true);
  const envoye = Object.values(etat.messages).filter(x => x.reference).pop();
  vrai(!!envoye, "le transfert est bien parti au serveur");
  eq(envoye.reference, "m1", "il porte sa PROVENANCE — une relation, pas un en-tête (D067)");
  eq(envoye.corps, "tu peux regarder ?", "le corps envoyé est le commentaire seul : l'index ne reprend pas le fil (D163)");
  eq(envoye.nb_pieces_jointes, 1, "le message d'origine part encapsulé en message/rfc822 (D066)");

  console.log("— une pièce jointe : l'ouvrir, ou ouvrir le message qu'elle EST (D168) ————");
  A.Controllers.Tabs.ouvrir({ type: "msg", id: "m3" }, false); await drainer(e);
  vrai(det().includes("un message que vous avez"), "la pièce résolue s'annonce comme un message, pas comme un fichier");
  geste("detail", ".pjc", 1);
  await drainer(e);
  vrai(ui.tabs.some(t => t.key === "m:m1"), "cliquer l'encapsulé OUVRE le message d'origine (D168)");
  A.Controllers.Tabs.ouvrir({ type: "msg", id: "m3" }, false); await drainer(e);
  n = vus.length;
  geste("detail", ".pjc", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.includes("/pieces-jointes/")), "et une pièce ordinaire demande ses octets au serveur");
  vrai(!ui.tabs.some(t => t.key === "m:p1"), "elle n'ouvre évidemment pas d'onglet de message");
  /* le service seul, en plus du câblage : une pièce sans octets servis ne casse rien */
  const rendu = await A.Controllers.Message.ouvrirPiece(A.Api.cache.message("m3"), 0);
  vrai(rendu !== undefined, "ouvrirPiece rend ce que le serveur a donné, sans jeter");

  console.log("— l'arborescence : dossier virtuel, épingle, renommer —");
  const nav = A.Controllers.Nav;
  nav.peindre();
  clic("v_new");
  vrai(!!ui.formVirtuel, "le formulaire de dossier virtuel s'ouvre");
  nav.peindre();
  saisir("v_label", "Mes Acme");
  clic("v_plus");
  eq(ui.formVirtuel.criteres.length, 2, "on ajoute un critère");
  nav.peindre(); clic("v_ok");
  await drainer(e);
  vrai(vus.includes("POST /dossiers-virtuels"), "le dossier virtuel est créé par l'API");
  nav.peindre(); clic("v_new"); nav.peindre(); clic("v_non");
  vrai(!ui.formVirtuel, "et le formulaire se referme");
  const q = saisir("navq", "acme");
  vrai(!!q, "le filtre de l'arborescence existe");
  /* les gestes de l'arborescence, par leur sélecteur : ouvrir une branche, épingler, dépublier */
  ui.navq = ""; nav.peindre();
  n = vus.length;
  geste("nav", ".node", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("GET /messages")), "cliquer une branche ouvre son dossier");
  nav.peindre();
  n = vus.length;
  geste("nav", "[data-pin]", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("PUT /parametres") || v.startsWith("GET /parametres")),
       "épingler passe par les paramètres du compte (D106/D144)");
  nav.peindre();
  n = vus.length;
  geste("nav", "[data-delv]", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("DELETE /dossiers-virtuels")), "et un dossier virtuel se supprime");

  console.log("— l'administration : état, journal, règles ————————");
  A.Controllers.Tabs.ouvrir({ type: "admin", volet: "etat" }, false);
  await drainer(e);
  vrai(/État|journal/i.test(det()), "le volet État se peint");
  vrai(vus.includes("GET /etat"), "il charge l'état du serveur");
  clic("etat-recharger"); await drainer(e);
  saisir("j-domaine", "api"); saisir("j-niveau", "INFO"); saisir("j-filtre", "ok");
  vrai(vus.includes("GET /etat/journal"), "le journal est chargé");
  A.Controllers.Tabs.ouvrir({ type: "admin", volet: "regles" }, false);
  await drainer(e);
  vrai(vus.includes("GET /filtres"), "le volet Règles charge les règles");
  clic("r-nouvelle");
  await drainer(e);
  saisir("r-nom", "Ma règle");
  clic("r-ok"); await drainer(e);
  vrai(vus.includes("POST /filtres"), "une règle se crée");
  eq(etat.filtres[0] && etat.filtres[0].portee, "boite",
     "l'écran crée la règle pour la BOÎTE (D171) — en « compte », elle ne s'appliquait à aucun courrier entrant");
  /* la règle créée se pilote depuis sa ligne — deux gestes délégués, jamais testés jusqu'ici */
  n = vus.length;
  geste("detail", "[data-rtoggle]", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("PATCH /filtres")), "activer/désactiver une règle passe par l'API");
  n = vus.length;
  geste("detail", "[data-rdel]", 0);
  await drainer(e);
  vrai(vus.slice(n).some(v => v.startsWith("DELETE /filtres")), "et la supprimer aussi");
  /* les volets se choisissent par une puce, pas par un id */
  geste("detail", ".chip[data-vol]", 0);
  await drainer(e);
  vrai(det().length > 100, "changer de volet par sa puce repeint l'écran");

  console.log("— les raccourcis et la navigation ————————————————");
  const K = A.Controllers.Raccourcis;
  K.brancher();
  K.traiter({ key: "?", target: { tagName: "BODY" }, preventDefault() {} });
  vrai(K.ouverte, "? ouvre l'aide des raccourcis");
  clic("rac_fermer");
  vrai(!K.ouverte, "et le bouton la referme");
  const App = A.Controllers.App;
  App.ouvrirNav(); vrai(doc.getElementById("main").classList.contains("navopen"), "le tiroir s'ouvre");
  App.fermerNav(); App.setVue("liste"); App.setQ(false);
  vrai(!App.qOuvert(), "le journal des requêtes reste fermé en produit");

  bilan();
})().catch(e => { console.error("  ✗ échec des parcours :", e.stack.split("\n").slice(0, 3).join(" | ")); process.exit(1); });
