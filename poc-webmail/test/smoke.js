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
vrai(q.sql.includes("pg_notify"), "les externes passent au relais");

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
