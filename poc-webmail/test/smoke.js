/* Parcours fonctionnel complet : ouverture, onglets, actions, composition,
   persistance et rechargement. */
"use strict";
const { demarrer, creerStockage, eq, vrai, bilan } = require("./run");
const { evt } = require("./fake-dom");

const clic = (el, e) => el.onclick && el.onclick(e || evt(el));

console.log("— chargement ————————————————————————————————");
const ls = creerStockage();
let p = demarrer(ls);
let A = p.ABX;
eq(p.fichiers.length, 28, "index.html déclare tous les scripts");
vrai(A.Corpus.tous.length > 3000, "corpus engendré (" + A.Corpus.tous.length + " messages)");
vrai(A.Registry.liste().length >= 15, "partielles enregistrées : " + A.Registry.liste().length);
vrai(p.doc.getElementById("nav").innerHTML.includes("Fournisseurs"), "arborescence peinte");
vrai(p.doc.getElementById("list").innerHTML.includes("msg"), "liste peinte");

console.log("— surcharge de vues partielles ——————————————————");
const nSurcharges = A.Registry.liste().filter(n => n.includes("@")).length;
vrai(nSurcharges >= 5, nSurcharges + " partielles spécialisées");
const notif = A.Corpus.tous.find(m => m.fid.startsWith("notification:"));
const client = A.Corpus.tous.find(m => m.fid.startsWith("client:"));
eq(A.Views.List.variante(notif), "notification", "variante déduite de l'axe");
eq(A.Views.List.variante(client), null, "pas de variante pour un axe sans surcharge");
const cardNotif = A.Registry.render("message.card", { m: notif, variant: "notification" });
const cardBase  = A.Registry.render("message.card", { m: notif });
vrai(!cardNotif.includes("snip"), "la carte notification n'affiche pas le snippet");
vrai(cardBase.includes("snip"), "la carte de base, si");
const envoye = A.Corpus.tous.find(m => m.fid === "sent");
vrai(A.Registry.render("message.card", { m: envoye, variant: "sent" }).includes("À :"),
     "la carte du dossier Envoyés montre le destinataire");

console.log("— ouverture d'un dossier et onglets —————————————");
const dossier = A.Fixtures.valeurs.client[0];
A.Controllers.List.ouvrir({ id: dossier.id, label: dossier.label, kind: "virtuel", axe: "client" });
const lignes = p.doc.getElementById("list").querySelectorAll(".msg");
vrai(lignes.length > 0, lignes.length + " messages listés");
clic(lignes[0]); clic(lignes[1]);
eq(A.Store.ui.tabs.length, 1, "le second clic remplace l'onglet provisoire");
lignes[1].ondblclick(); clic(lignes[2]);
eq(A.Store.ui.tabs.length, 2, "un onglet épinglé n'est pas remplacé");
vrai(p.doc.getElementById("tabs").innerHTML.includes("class=\"tab"), "barre d'onglets peinte");

console.log("— actions réelles ————————————————————————————");
const cible = A.Corpus.par(lignes[3].dataset.id);
eq(cible.lu, cible.lu, "état initial lu = " + cible.lu);
A.MessageService.archiver(cible);
eq(cible.motif, "archive", "archivé");
vrai(A.Corpus.cnt("archives").t >= 1, "la vue Archives compte le message");
vrai(A.Corpus.vue({ id: dossier.id, kind: "virtuel" }).includes(cible),
     "un message archivé reste dans son dossier");
const enFile = A.Corpus.filtrer({ id: dossier.id, kind: "virtuel" }, "file", "date_desc");
vrai(!enFile.includes(cible), "il a quitté la file");
A.MessageService.corbeille(cible);
eq(cible.dossier, "trash", "mis à la corbeille");
vrai(A.Corpus.vue({ id: "trash", kind: "special" }).includes(cible), "visible dans la corbeille");
A.MessageService.supprimer(cible);
vrai(!A.Corpus.tous.includes(cible), "supprimé définitivement");

console.log("— composition ————————————————————————————————");
const src = A.Corpus.par(lignes[0].dataset.id);
A.Controllers.Compose.demarrer("rep", src);
let t = A.Store.ui.tabs.find(x => x.type === "compo");
vrai(!!t, "onglet de composition ouvert");
eq(t.data.de, src.boite, "l'identité d'envoi est celle de la boîte qui a reçu (Q26)");
vrai(t.data.sujet.startsWith("Re: "), "sujet préfixé");
vrai(t.data.corps.includes("> "), "corps cité");
t.data.a = "collegue@iprospective.eu, client@exemple.fr";
A.ComposeService.joindre(t.data);
eq(t.data.pjs.length, 1, "pièce jointe ajoutée");
const avant = A.Corpus.dossiers.sent.length;
A.Controllers.Compose.finir(t, true);
eq(A.Corpus.dossiers.sent.length, avant + 1, "message envoyé, présent dans Envoyés");
const envoi = A.Corpus.dossiers.sent[0];
eq(envoi.pj, 1, "la pièce jointe a suivi");
const q = A.QueryLog.entrees.find(x => x.label.startsWith("Envoyer"));
vrai(!!q, "l'envoi est journalisé");
vrai(q.warn === true, "destinataires mixtes : l'avertissement D12 est levé");
vrai(q.enfants.length >= 4, "l'envoi est décomposé en " + q.enfants.length + " requêtes");
vrai(q.enfants.some(e => e.sql.includes("pg_notify")), "les externes passent au relais");
vrai(q.enfants.some(e => e.sql.includes("'recu'")), "les internes sont livrés en base");
vrai(q.enfants.some(e => e.warn), "l'étage mixte porte l'avertissement");

console.log("— transfert par référence ————————————————————————");
A.Controllers.Compose.demarrer("tr", src);
t = A.Store.ui.tabs.find(x => x.type === "compo");
eq(t.data.ref, true, "transfert par référence par défaut");
t.data.a = "collegue@iprospective.eu";
A.Controllers.Compose.finir(t, true);
eq(A.Corpus.dossiers.sent[0].ref, src.id, "le message porte un lien, pas une copie");
eq(A.Corpus.dossiers.sent[0].pj, 0, "aucune pièce jointe recopiée");

console.log("— brouillon ——————————————————————————————————");
A.Controllers.Compose.demarrer("new", null);
t = A.Store.ui.tabs.find(x => x.type === "compo");
t.data.sujet = "Un brouillon"; t.data.corps = "à finir";
A.Controllers.Compose.finir(t, false);
const br = A.Corpus.dossiers.drafts[0];
eq(br.subject, "Un brouillon", "brouillon enregistré");
vrai(!!br.compo, "il se rouvrira en composition");

console.log("— persistance et rechargement ————————————————————");
const nRatt = Object.keys(A.Store.ratt).length, nCrees = A.Store.crees.length;
vrai(nRatt > 0, nRatt + " rattachement(s) persistés");
vrai(A.Store.tailleKo() < 60, "état local léger : " + A.Store.tailleKo() + " ko");

const p2 = demarrer(ls);           // même localStorage = rechargement de la page
const B = p2.ABX;
eq(B.Corpus.tous.length > 3000, true, "corpus réengendré");
eq(Object.keys(B.Store.ratt).length, nRatt, "delta repris");
eq(B.Store.crees.length, nCrees, "messages écrits repris");
vrai(B.Corpus.dossiers.drafts.some(m => m.subject === "Un brouillon"), "le brouillon a survécu");
vrai(!B.Corpus.tous.some(m => m.id === cible.id), "le message supprimé n'est pas ressuscité");
vrai(B.Store.ui.tabs.length > 0, "les onglets sont restaurés");
const m0 = B.Corpus.par(lignes[0].dataset.id);
eq(m0.lu, true, "le message lu la session précédente est toujours lu");

console.log("— sens : reçus / envoyés —————————————————————————");
const dossierAxe = { id: dossier.id, label: dossier.label, kind: "virtuel", axe: "client" };
const contenu = A.Corpus.vue(dossierAxe);
const sortants = contenu.filter(m => m.sens === "out");
vrai(sortants.length > 0, sortants.length + " sortants dans un dossier client sur " + contenu.length);
vrai(sortants.length < contenu.length, "et des entrants aussi");
eq(A.Corpus.filtrer(dossierAxe, "file", "date_desc", "out").every(m => m.sens === "out"), true,
   "le filtre « envoyés » ne garde que les sortants");
eq(A.Corpus.filtrer(dossierAxe, "file", "date_desc", "in").every(m => m.sens === "in"), true,
   "et « reçus » que les entrants");
const croise = A.Corpus.filtrer(dossierAxe, "non_lus", "date_desc", "in");
eq(croise.every(m => !m.lu && m.sens === "in"), true, "sens et filtre se CROISENT");
eq(A.Views.List.variante(sortants[0]), "sent",
   "un sortant s'affiche comme dans Envoyés, quel que soit son dossier");
vrai(A.Registry.render("message.card", { m: sortants[0], variant: "sent" }).includes("À :"),
     "sa carte montre le destinataire");
A.Controllers.List.logSens("out");
const qs = A.QueryLog.entrees[0];
vrai(qs.warn, "le journal avertit : le sens doit être une colonne, pas une déduction");
vrai(qs.sql.includes("r.sens"), "la requête s'appuie sur r.sens");

console.log("— tags ————————————————————————————————————————");
const mt = A.Corpus.par(lignes[0].dataset.id);
const nTags = mt.tags.length;
A.MessageService.ajouterTag(mt, "projet", "RM2937");
eq(mt.tags.length, nTags + 1, "tag ajouté");
eq(mt.tags[mt.tags.length - 1].src, "utilisateur", "posé par l'utilisateur");
A.MessageService.ajouterTag(mt, "projet", "RM2937");
eq(mt.tags.length, nTags + 1, "un doublon exact n'est pas reposé");
A.MessageService.ajouterTag(mt, "projet", "  ");
eq(mt.tags.length, nTags + 1, "une valeur vide est refusée");
const iAuto = mt.tags.findIndex(t => t.src === "dolibarr-mmi");
if (iAuto >= 0) { A.MessageService.retirerTag(mt, iAuto);
  vrai(A.QueryLog.entrees[0].warn, "retirer un tag de connecteur lève un avertissement"); }
const iUser = mt.tags.findIndex(t => t.src === "utilisateur");
A.MessageService.retirerTag(mt, iUser);
vrai(!mt.tags.some(t => t.val === "RM2937"), "tag retiré");
vrai(!!A.Store.ratt[mt.id].tags, "les tags sont dans le delta persisté");

console.log("— quarantaine ————————————————————————————————");
const spam = A.Corpus.par(lignes[4].dataset.id);
A.MessageService.junk(spam);
eq(spam.dossier, "junk", "mis en quarantaine");
const qj = A.QueryLog.entrees[0];
eq(qj.enfants.length, 2, "le geste classe ET apprend");
vrai(qj.enfants.some(e => e.sql.includes("apprentissage_spam")), "l'apprentissage est journalisé");
vrai(A.Views.Message.actionsEtat(spam).includes("nonJunk"),
     "la barre propose « ce n'est pas un indésirable »");
vrai(!A.Views.Message.actionsEtat(spam).includes('data-x="junk"'),
     "et ne propose plus de le remarquer indésirable");
A.MessageService.nonJunk(spam);
eq(spam.dossier, null, "sorti de la quarantaine");
vrai(A.QueryLog.entrees[0].enfants.some(e => e.sql.includes("'ham'")), "le filtre désapprend");

console.log("— requêtes imbriquées ————————————————————————————");
A.Controllers.Message.logErp(client, "inv");
const api = A.QueryLog.entrees[0];
eq(api.kind, "api", "entrée marquée API");
vrai(api.sql.startsWith("GET "), "le parent est l'appel HTTP");
eq(api.enfants.length, 1, "et porte la requête SQL qu'il déclenche");
vrai(api.enfants[0].sql.includes("SELECT"), "laquelle est bien du SQL");
vrai(api.enfants[0].index.includes("portée"), "avec son propre index et son avertissement");
const rendu = A.Views.QueryLog.render(A.QueryLog.entrees);
vrai(rendu.includes("class=\"sub\""), "la vue rend le bloc imbriqué");
vrai(rendu.includes("requête(s) déclenchée(s)"), "et l'annonce");
A.Controllers.Message.logErp(client, "res");
vrai(A.QueryLog.entrees[0].enfants.length === 3, "un geste non-API peut aussi être décomposé");
vrai(!A.QueryLog.entrees[0].sql, "son parent n'a pas de requête propre");

console.log("— déterminisme ————————————————————————————————");
const p3 = demarrer(creerStockage());   // stockage vierge
const C = p3.ABX;
eq(C.Corpus.tous.length, 
   demarrer(creerStockage()).ABX.Corpus.tous.length, "deux amorçages donnent le même corpus");
const f1 = C.Erp.fiche("client", A.Fixtures.valeurs.client[0].label);
const f2 = demarrer(creerStockage()).ABX.Erp.fiche("client", A.Fixtures.valeurs.client[0].label);
eq(f1.ref, f2.ref, "les fiches ERP sont reproductibles");
eq(f1.encours, f2.encours, "leurs montants aussi");

bilan();
