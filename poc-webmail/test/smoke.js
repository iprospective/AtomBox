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
vrai(p.fichiers.length > 25, p.fichiers.length + " scripts déclarés par index.html");
vrai(A.Corpus.tous.length > 3000, "corpus engendré (" + A.Corpus.tous.length + " messages)");
vrai(A.Registry.liste().length >= 15, "partielles enregistrées : " + A.Registry.liste().length);
vrai(p.doc.getElementById("nav").innerHTML.includes("Fournisseurs"), "arborescence peinte");
vrai(p.doc.getElementById("list").innerHTML.includes("msg"), "liste peinte");

console.log("— expéditeur normalisé (D126) et usurpation (D128) —————");
const ent = A.Corpus.tous.filter(m => m.sens !== "out");
const connu = ent.find(m => m.connu);
const inconnu = ent.find(m => !m.connu && !m.spoof);
const usurpe = ent.find(m => m.spoof);
vrai(!!connu && !!inconnu && !!usurpe, "le corpus porte les trois cas");
const hCon = A.Registry.render("expediteur", { m: connu });
const hInc = A.Registry.render("expediteur", { m: inconnu });
const hUsu = A.Registry.render("expediteur", { m: usurpe });
vrai(hCon.includes(connu.from) && !hCon.includes("adr-av"),
     "un correspondant connu s'affiche par son nom de carnet");
vrai(hInc.includes(inconnu.mail) && hInc.includes("adr-av"),
     "un inconnu s'affiche par son ADRESSE, mise en avant");
vrai(hInc.includes("«"), "et son nom déclaré est relégué entre guillemets");
vrai(hUsu.includes("usurpe"), "l'usurpation par nom porte son signal");
vrai(!A.Views.Message.spoofHtml(inconnu),
     "aucun bandeau sur un simple inconnu — le silence est une fonctionnalité");
vrai(A.Views.Message.spoofHtml(usurpe).includes("B1"),
     "le bandeau nomme la règle qui l'a déclenché");
vrai(usurpe.mail.split("@")[1] !== connu.mail.split("@")[1],
     "l'adresse usurpatrice est sur un autre domaine que le carnet");

console.log("— nature du message (D130) et refus de réponse (D131) ——");
const diff = ent.find(m => m.nature === "liste");
const noti = ent.find(m => m.nature === "notification");
const refus = ent.find(m => m.repond === "non");
vrai(!!diff && !!noti && !!refus, "le corpus porte les trois cas de nature");
vrai(diff.mail.startsWith("news@") && noti.mail.startsWith("noreply@"),
     "une machine écrit depuis une boîte fonctionnelle, pas depuis une personne");
vrai(!diff.connu && !noti.connu,
     "une boîte fonctionnelle n'est jamais un correspondant du carnet");
const hDiff = A.Registry.render("expediteur", { m: diff });
vrai(!hDiff.includes("adr-av"),
     "une diffusion n'est PAS affichée comme un inconnu suspect");
vrai(hDiff.includes("diffusion"), "sa nature est dite, en clair");
vrai(A.Corpus.tous.every(m => m.nature !== "liste" || m.statut === "nouveau"),
     "aucune diffusion n'entre dans la file de travail (D130)");
vrai(A.Corpus.tous.some(m => m.nature === "notification" && m.statut !== "nouveau"),
     "des notifications y entrent — une facture attend un paiement");
vrai(!A.Views.Message.repondHtml(connu),
     "aucun bandeau de réponse sur un message humain");
vrai(A.Views.Message.repondHtml(diff).includes("désabonner"),
     "sur une diffusion, l'action utile proposée est le désabonnement (D132)");
const hRefus = A.Views.Message.repondHtml(refus);
vrai(hRefus.includes("550") && /il y a \d+ jours/.test(hRefus),
     "un refus s'appuie sur un rejet DATÉ, pas sur le mot « noreply » (D131)");
vrai(A.Corpus.tous.every(m => m.repond !== "non" || m.nature !== "humain"),
     "on ne refuse jamais la réponse à un message écrit par une personne");

console.log("— cohérence du CDC lui-même (dictionnaire, ch. 16) —————");
{
  const D = A.CDC.dict, ids = new Set(A.CDC.decisions.map(d => d.id)),
        qs = new Set(A.CDC.questions.map(q => q.id));
  const ents = new Set(D.entites.map(e => e.id));
  vrai(D.entites.length >= 25 && D.fonctionnalites.length >= 90,
       D.entites.length + " entités, " + D.fonctionnalites.length + " fonctionnalités, " +
       D.actions.length + " actions, " + D.routes.length + " routes, " + D.normes.length + " normes");
  const cs = new Set((A.CDC.conseils || []).map(c => c.id));
  vrai(cs.size >= 5, cs.size + " conseils (C) dans l'index — ils font partie du registre");
  const refsInconnues = [];
  const verif = (liste, nom) => liste.forEach(x => {
    const qui = nom + ":" + (x.id || x.nom || x.libelle || x.chemin);
    (x.decisions || []).forEach(d => { if (!ids.has(d)) refsInconnues.push(qui + "→" + d); });
    (x.questions || []).forEach(q => { if (!qs.has(q)) refsInconnues.push(qui + "→" + q); });
    (x.conseils  || []).forEach(c => { if (!cs.has(c)) refsInconnues.push(qui + "→" + c); });
  });
  verif(D.fonctionnalites, "fonctionnalité"); verif(D.entites, "entité"); verif(D.actions, "action");
  verif(D.routes, "route"); verif(D.protocoles, "protocole"); verif(D.workflows, "workflow");
  eq(refsInconnues.length, 0, "chaque décision, question ou conseil cité par le dictionnaire existe au registre" +
     (refsInconnues.length ? " — inconnues : " + refsInconnues.slice(0, 5).join(", ") : ""));
  const relCassees = D.relations.filter(r => !ents.has(r.de) || !ents.has(r.vers)).map(r => r.de + "→" + r.vers);
  eq(relCassees.length, 0, "chaque relation relie deux entités déclarées" +
     (relCassees.length ? " — " + relCassees.join(", ") : ""));
  const champsOrphelins = Object.keys(D.champs).filter(e => !ents.has(e));
  eq(champsOrphelins.length, 0, "chaque bloc de champs appartient à une entité déclarée");
  const enums = new Set(Object.keys(D.enumerations));
  const enumInconnus = [];
  Object.values(D.champs).forEach(l => l.forEach(c => { if (c.enum && !enums.has(c.enum)) enumInconnus.push(c.nom + "→" + c.enum); }));
  eq(enumInconnus.length, 0, "chaque champ enum pointe une énumération déclarée" +
     (enumInconnus.length ? " — " + enumInconnus.join(", ") : ""));
  const routesEnt = D.routes.flatMap(r => r.entites || []).filter(e => !ents.has(e));
  eq(routesEnt.length, 0, "chaque route nomme des entités déclarées" + (routesEnt.length ? " — " + routesEnt.join(", ") : ""));
  vrai(D.jalons.every(j => (j.contenu || []).length > 0), "aucun jalon vide");
  const trancheeCitee = D.fonctionnalites.filter(f => f.etat === "à trancher" &&
    (f.questions || []).every(q => { const x = A.CDC.questions.find(y => y.id === q); return x && x.urgence === "tranchee"; }) &&
    (f.questions || []).length);
  eq(trancheeCitee.length, 0, "une fonctionnalité « à trancher » cite une question encore ouverte" +
     (trancheeCitee.length ? " — " + trancheeCitee.map(f => f.id).join(", ") : ""));
  const tplCites = new Set(D.templates.map(t => t.nom));
  const tplManquants = A.Registry.liste().filter(n => !n.includes("@") && !tplCites.has(n));
  eq(tplManquants.length, 0, "chaque partielle du registre est décrite au dictionnaire" +
     (tplManquants.length ? " — " + tplManquants.join(", ") : ""));
  vrai(A.Views.Pages.FEATURES.length >= 8 && A.Views.Pages.ROADMAP.length === D.jalons.length,
       "la page Fonctionnalités et la Roadmap sont lues dans le dictionnaire, pas saisies");
  const p = A.Views.Pages.render("features");
  vrai(p.includes(D.fonctionnalites[D.fonctionnalites.length - 1].libelle),
       "la dernière fonctionnalité du dictionnaire est affichée");
}

console.log("— le pivot comm dans les requêtes (D138) ——————————————");
{
  A.QueryLog.vider && A.QueryLog.vider();
  const d = A.Fixtures.valeurs.client[0];
  A.Controllers.List.ouvrir({ id: d.id, label: d.label, kind: "virtuel", axe: "client" });
  const tout = JSON.stringify(A.QueryLog.entrees);
  vrai(/JOIN comm /.test(tout), "les requêtes lisent le tronc `comm`");
  const q = A.QueryLog.entrees.find(e => e.label.startsWith("Ouvrir"));
  vrai(!JSON.stringify(q).includes("comm_email"),
       "ouvrir un dossier ne joint PAS la fille — c'est tout l'intérêt de D138");
  vrai(!/FROM message\b|JOIN message\b/.test(tout),
       "plus aucune requête ne nomme une table `message`");
}

console.log("— fiabilité de l'expéditeur (D136, D137) ——————————————");
{
  const t = A.Corpus.tous;
  const valide  = t.find(m => m.fiab >= 2);
  const nonAlig = t.find(m => m.sens !== "out" && m.dom && !m.dom.aligne && m.connu);
  vrai(!!valide && !!nonAlig, "le corpus porte un expéditeur validé et un connu non aligné");
  vrai(A.Registry.render("fiabilite", { m: valide }).includes("fiab f2"),
       "l'expéditeur validé porte son indicateur");
  vrai(!A.Registry.render("fiabilite", { m: nonAlig }),
       "AUCUN indicateur sur un message non authentifié, même d'un correspondant connu");
  vrai(t.every(m => !(m.fiab >= 1) || (m.dom && m.dom.aligne)),
       "aucune fiabilité positive sans alignement du domaine (D137)");
  vrai(t.every(m => !m.spoof || m.fiab < 0),
       "une usurpation porte une fiabilité négative — même échelle, deux directions");
  const h = A.Views.Message.fiabiliteHtml(nonAlig);
  vrai(h.includes("disabled"),
       "on ne peut pas valider une adresse depuis un message non authentifié");
  vrai(A.Views.Message.fiabiliteHtml(valide).includes("D128"),
       "le bandeau dit que la validation ne fait pas taire les règles fortes");
  const connuAlig = t.find(m => m.fiab === 1);
  vrai(A.Views.Message.fiabiliteHtml(connuAlig).includes("cette boîte"),
       "la validation annonce sa portée par défaut (D106)");
  vrai(!A.Views.Message.fiabiliteHtml(t.find(m => m.spoof)),
       "aucun bandeau de confiance sur une usurpation — le bandeau d'alerte suffit");
}

console.log("— ordre des dossiers (D135) ——————————————————————");
{
  const ui = A.Store.ui, nav0 = A.Views.Nav.render(ui);
  vrai(!nav0.includes("Tous —"), "plus de préfixe « Tous — » sur le nœud d'axe");
  vrai(!nav0.includes('class="grp">Fournisseurs'),
       "ni de titre de groupe qui répétait le nom juste au-dessus");
  vrai(nav0.includes("axops"), "les commandes d'ordre sont dans le nœud d'axe");
  const premier = A.Fixtures.AXES[0].id, second = A.Fixtures.AXES[1].id;
  ui.ordreAxes = A.Fixtures.AXES.map(a => a.id);
  const ordre = ui.ordreAxes;
  ordre[0] = second; ordre[1] = premier;
  const nav1 = A.Views.Nav.render(ui);
  vrai(nav1.indexOf("axe:" + second) < nav1.indexOf("axe:" + premier),
       "l'axe remonté passe devant");
  ui.ordreAxes = null;
  const axe = A.Fixtures.AXES.find(a => a.id === "fournisseur");
  ui.ouverts[axe.id] = true;
  ui.triAxe[axe.id] = "alpha";
  ui.plus[axe.id] = true;                       // tout afficher, pas les 12 premiers
  const alpha = A.Views.Nav.render(ui);
  const tries = A.Fixtures.valeurs[axe.id].map(v => v.label)
                  .sort((x, y) => x.localeCompare(y));
  const pos = lb => alpha.indexOf(">" + A.Fmt.esc(lb) + "<");
  vrai(pos(tries[0]) > 0 && pos(tries[0]) < pos(tries[tries.length - 1]),
       "le tri A→Z ordonne les dossiers de l'axe");
  ui.triAxe = {}; ui.ouverts = {}; ui.plus = {};
}

console.log("— abonnements : un dossier par liste (D133) ——————————");
const abos = A.Fixtures.valeurs.abonnement;
vrai(abos.length >= 10, abos.length + " dossiers d'abonnement déduits du corpus");
vrai(abos.every(v => v.label && v.id.startsWith("abonnement:")),
     "chacun porte le nom de sa liste");
const abo = abos[0];
const dansAbo = A.Corpus.vue({ id: abo.id, kind: "abo" });
vrai(dansAbo.length > 0, "le dossier « " + abo.label + " » contient " + dansAbo.length + " messages");
vrai(dansAbo.every(m => m.nature === "liste"), "et rien d'autre que des diffusions");
const unAbo = dansAbo[0];
vrai(A.Corpus.vue({ id: unAbo.fid, kind: "virtuel" }).includes(unAbo),
     "le message est AUSSI dans le dossier de son correspondant — il n'a pas bougé (D77)");
vrai(A.Corpus.cnt(abo.id).t === dansAbo.length,
     "les compteurs de la branche dérivée sont calculés dans la même passe (D78)");
vrai(A.Corpus.cnt("axe:abonnement").t ===
     A.Corpus.tous.filter(m => m.nature === "liste").length,
     "« Tous — Abonnements » compte toutes les diffusions");
vrai(A.Views.Nav.render(A.Store.ui).includes("Abonnements"),
     "l'axe apparaît dans l'arborescence");

console.log("— surcharge de vues partielles ——————————————————");
const nSurcharges = A.Registry.liste().filter(n => n.includes("@")).length;
vrai(nSurcharges >= 5, nSurcharges + " partielles spécialisées");
const notif = A.Corpus.tous.find(m => m.fid.startsWith("notification:"));
/* Un message SORTANT prend toujours la variante « sent » : pour tester l'absence
   de surcharge d'axe, il faut un entrant — sinon le test dépend de l'ordre du corpus. */
const client = A.Corpus.tous.find(m => m.fid.startsWith("client:") && m.sens !== "out");
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
const det = e => (e.detail || "");
vrai(!!q, "l'envoi est journalisé");
vrai(q.warn === true, "destinataires mixtes : l'avertissement D12 est levé");
vrai(q.etapes.length >= 5, "l'envoi est décomposé en " + q.etapes.length + " étapes");
vrai(q.etapes.some(e => det(e).includes("pg_notify")), "les externes passent au relais");
vrai(q.etapes.some(e => det(e).includes("'recu'")), "les internes sont livrés en base");
vrai(q.etapes.some(e => e.warn), "l'étage mixte porte l'avertissement");

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
vrai(qs.warn, "la trace avertit : le sens doit être une colonne, pas une déduction");
vrai(qs.etapes.some(e => (e.detail || "").includes("r.sens")), "la requête s'appuie sur r.sens");

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
eq(qj.etapes.filter(e => e.t === "sql").length, 2, "le geste classe ET apprend");
vrai(qj.etapes.some(e => (e.detail || "").includes("apprentissage_spam")),
     "l'apprentissage est tracé");
const barre = A.Views.Message.render(spam, A.Store.ui);
vrai(barre.includes('data-x="nonJunk"'), "la barre propose « ce n'est pas un indésirable »");
vrai(!barre.includes('data-x="junk"'), "et ne propose plus de le remarquer indésirable");
A.MessageService.nonJunk(spam);
eq(spam.dossier, null, "sorti de la quarantaine");
vrai(A.QueryLog.entrees[0].etapes.some(e => (e.detail || "").includes("'ham'")),
     "le filtre désapprend");

console.log("— cascade d'ouverture d'un message ————————————————");
const cible2 = A.Corpus.tous.find(x => x.fid.startsWith("client:") && x.pj && x.tags.length && !x.lu);
A.QueryLog.vider();
A.Controllers.Tabs.ouvrir({ type: "msg", id: cible2.id }, false);
const tr = A.QueryLog.entrees.find(x => x.label.startsWith("Ouvrir «"));
vrai(!!tr, "la cascade est tracée");
const types = tr.etapes.map(e => e.t);
["ui","cache","http","route","ctrl","acl","sql","blob","json","render"].forEach(t =>
  vrai(types.includes(t), "étape « " + t + " » présente"));
vrai(types.indexOf("ui") < types.indexOf("http"), "le clic précède l'appel");
vrai(types.indexOf("http") < types.indexOf("sql"), "l'appel précède les requêtes");
vrai(types.lastIndexOf("json") < types.lastIndexOf("render"), "le JSON précède le rendu");
const js = tr.etapes.find(e => e.t === "json");
const contrat = JSON.parse(js.detail);
eq(contrat.comm_id, cible2.id, "le JSON porte l'identifiant");
["sujet","de","a","boite","sens","date_reception","lu_le","sorti_le","thread_id",
 "taille_octets","nb_pieces_jointes","tags","pieces_jointes","corps"].forEach(k =>
  vrai(k in contrat, "contrat d'API : champ « " + k + " »"));
eq(contrat.pieces_jointes.length, cible2.pj, "les pièces jointes y sont");
vrai("mime_declare" in contrat.pieces_jointes[0] && "mime_detecte" in contrat.pieces_jointes[0],
     "avec les deux types, déclaré et détecté (D32)");
vrai(tr.etapes.some(e => e.warn), "la cascade signale ses points coûteux");
vrai(tr.etapes.filter(e => e.t === "http").length >= 2,
     "un message tagué coûte un SECOND aller-retour, vers l'application (Q31)");
const rc = A.Views.QueryLog.render([tr]);
vrai(rc.includes("réseau — aller-retour") && rc.includes(">serveur<"),
     "la vue marque les passages de frontière");

console.log("— cascade ————————————————————————————————————————");
A.Controllers.Message.logErp(client, "inv");
const api = A.QueryLog.entrees[0];
vrai(api.etapes.some(e => e.t === "http"), "la trace contient l'appel HTTP");
vrai(api.etapes.some(e => e.t === "sql"), "et la requête qu'il déclenche");
vrai(api.etapes[0].detail.startsWith("GET "), "l'appel vient en premier");
const rendu = A.Views.QueryLog.render(A.QueryLog.entrees);
vrai(rendu.includes('class="casc"'), "la vue rend la cascade");
vrai(rendu.includes("réseau — aller-retour"), "et marque le passage du réseau");

console.log("— workflow de statut ————————————————————————————");
const w = A.Corpus.par(lignes[6].dataset.id);
eq(w.statut, w.statut, "statut initial : " + w.statut);
A.MessageService.statuer(w, "a_faire");
eq(w.statut, "a_faire", "passé à faire");
eq(w.motif, null, "à faire ne sort PAS de la file");
const qw = A.QueryLog.entrees[0];
vrai(qw.etapes.some(e => (e.detail || "").includes("SET statut")), "le statut est une colonne");
vrai(qw.etapes.some(e => e.t === "note" && (e.index || "").includes("un tag est ouvert")),
     "la trace explique pourquoi ce n'est pas un tag");
A.MessageService.statuer(w, "en_cours");
eq(w.statut, "en_cours", "puis en cours");
A.MessageService.statuer(w, "traite");
eq(w.motif, "traite", "« traité » sort de la file");
vrai(w.sorti > 0, "et pose sorti_le");
vrai(A.QueryLog.entrees[0].etapes.some(e => e.warn), "en avertissant du changement de partition");
A.MessageService.statuer(w, "a_faire");
eq(w.motif, null, "revenir en arrière remet dans la file (Q09)");
vrai(A.Corpus.aFaire().includes(w), "il apparaît dans la file de travail");
eq(A.Corpus.filtrer(dossierAxe, "file", "date_desc", "tous", "en_cours")
    .every(m => m.statut === "en_cours"), true, "le filtre par statut fonctionne");
vrai(A.Corpus.cnt(w.fid).f >= 1, "les compteurs suivent la file de travail");

console.log("— capacités enfichables —————————————————————————");
const P = A.Providers;
eq(Object.keys(P.CAPACITES).length, 5, "cinq capacités : tâches, contacts, fichiers, calendrier, CRM");
eq(P.actif("taches").id, "dolibarr", "défaut V1 : un connecteur, pas le natif");
vrai(Object.keys(P.CAPACITES.contacts.fournisseurs).length >= 5,
     "contacts : aucun, natif, CardDAV, Dolibarr, LDAP");
vrai(Object.values(P.CAPACITES).every(c => c.fournisseurs.aucun),
     "chaque capacité peut être ABSENTE — c'est un état normal en V1");
eq(P.CAPACITES.taches.fournisseurs.natif.v, 3, "le composant interne est jalonné V3");
eq(P.CAPACITES.crm.fournisseurs.natif.v, 3, "le CRM interne aussi");
eq(P.CANAUX.filter(c => c.v === 4).length, 3, "trois canaux en V4 : SMS, WhatsApp, téléphonie");

A.QueryLog.vider();
A.Capacites.creerTache(client);
const td = A.QueryLog.entrees[0];
vrai(td.label.includes("Dolibarr"), "la trace nomme le fournisseur");
vrai(td.etapes.some(e => e.t === "http"), "en connecteur : un appel sortant");
vrai(td.etapes.some(e => e.warn), "et l'avertissement sur le lien qui peut mourir");
P.choisir("taches", "natif");
vrai(A.QueryLog.entrees.slice(0, 2).some(x => x.label.includes("aperçu")),
     "basculer sur le natif prévient : V3");
A.QueryLog.vider();
A.Capacites.creerTache(client);
const tn = A.QueryLog.entrees[0];
vrai(tn.etapes.every(e => e.t !== "http"), "en natif : aucun appel réseau");
vrai(tn.etapes.some(e => (e.detail || "").includes("INSERT INTO tache")), "une table locale");
eq(tn.etapes[0].label, td.etapes[0].label, "le geste de départ est le MÊME");
P.choisir("taches", "dolibarr");

console.log("— administration ————————————————————————————————");
A.Controllers.Admin.ouvrir("apps");
const adm = p.doc.getElementById("detail").innerHTML;
vrai(adm.includes("dolibarr-mmi"), "les applications sont listées");
vrai(adm.includes("abx_tk_"), "avec leurs jetons");
vrai(A.QueryLog.entrees[0].etapes.some(e => (e.index || "").includes("empreinte")),
     "et la trace rappelle qu'on ne stocke pas le secret");
A.Controllers.Admin.geste("tok:dolibarr-mmi");
vrai(A.QueryLog.entrees[0].label.includes("Révoquer"), "révocation tracée");
A.Controllers.Admin.ouvrir("suite");
const vs = p.doc.getElementById("detail").innerHTML;
vrai(vs.includes("Gestionnaire de tâches"), "le volet suite liste les capacités");
vrai(vs.includes("CRM"), "CRM compris");
vrai(vs.includes('class="jalon v3"'), "les composants internes sont marqués V3");
A.Controllers.Admin.ouvrir("canaux");
const vc = p.doc.getElementById("detail").innerHTML;
vrai(vc.includes("WhatsApp") && vc.includes("Téléphonie"), "le volet canaux annonce la V4");
vrai(vc.includes("message.canal"), "et les précautions de schéma à prendre dès la V1");
vrai(A.QueryLog.entrees[0].warn, "la trace insiste : ajouter la colonne en V4 coûte une migration");

console.log("— arborescence Développement (D77) ——————————————");
const tickets = A.Fixtures.valeurs.developpement;
vrai(tickets.length === 34, tickets.length + " tickets sous Développement");
vrai(/^RM\d+ · /.test(tickets[0].label), "un ticket est nommé RM<id> · titre");
const mdev = A.Corpus.tous.find(m => m.fid.startsWith("developpement:"));
vrai(!!mdev, "les tickets portent des messages");
const tdev = mdev.tags.find(t => t.axe === "developpement");
eq(tdev && tdev.src, "redmine-ipro", "le tag vient de Redmine, pas de l'ERP");
eq(A.Views.List.variante(mdev), "developpement", "la carte a sa variante");
vrai(A.Registry.render("message.card", { m: mdev, variant: "developpement" })
      .includes("RM"), "et elle met le numéro de ticket en avant");
const notifs = A.Corpus.tous.filter(m => m.fid.startsWith("notification:"));
vrai(notifs.every(m => m.sens !== "out"), "on n'envoie rien à une alerte de supervision");

console.log("— pièces jointes ————————————————————————————————");
A.Controllers.Admin.ouvrirPJ();
const vpj = p.doc.getElementById("detail").innerHTML;
vrai(vpj.includes("pjrow"), "la liste des pièces jointes est peinte");
vrai(vpj.includes("réellement stockés"), "avec le gain de déduplication");
const x0 = A.Views.Attachments.filtrer("", "tous")[0];
const blobAvant = x0.b.sha, refsAvant = x0.b.refs;
A.Controllers.Admin.renommer(x0, "facture-renommee.pdf");
eq(x0.p.nom, "facture-renommee.pdf", "renommé");
eq(x0.b.sha, blobAvant, "le blob n'a pas bougé");
eq(x0.b.refs, refsAvant, "ni ses liaisons");
const qr = A.QueryLog.entrees[0];
vrai(qr.etapes.some(e => (e.detail || "").includes("UPDATE comm_piece_jointe")),
     "c'est la liaison qui est modifiée");
vrai(qr.etapes.some(e => e.warn && (e.index || "").includes("pas de « partout »")),
     "et la trace dit ce qu'on ne peut PAS faire");
eq(A.Views.Attachments.filtrer("facture-renommee", "tous").length, 1, "la recherche le retrouve");

console.log("— barre du POC et pages —————————————————————————");
const nav = p.doc.querySelectorAll(".pocnav [data-page]");
eq(nav.length, 4, "quatre entrées dans la barre du POC");
nav.forEach(b => { b.onclick(); });
eq(A.Store.ui.tabs.filter(t => t.type === "page").length, 1,
   "les pages partagent UN onglet, elles ne s'empilent pas");
["aide","features","cdc","roadmap"].forEach(pg => {
  A.Controllers.Pages.ouvrir(pg);
  const h = p.doc.getElementById("detail").innerHTML;
  vrai(h.length > 800, "page « " + pg + " » : " + h.length + " octets");
  vrai(!h.includes("undefined"), "page « " + pg + " » sans undefined");
});
A.Controllers.Pages.ouvrir("cdc");
const hc = p.doc.getElementById("detail").innerHTML;
vrai(!!A.CDC, "index du CDC chargé");
vrai(A.CDC.decisions.length >= 90, A.CDC.decisions.length + " décisions indexées");
vrai(A.CDC.questions.length >= 30, A.CDC.questions.length + " questions indexées");
/* Le nombre de chapitres bouge a chaque lot : on verifie que l'index en porte
   assez et que le dernier du CDC y figure, pas un compte fige. */
vrai(A.CDC.chapitres.length >= 17,
     A.CDC.chapitres.length + " chapitres indexes");
vrai(A.CDC.chapitres.every(c => c.n && c.titre && c.fichier),
     "chaque chapitre indexe porte un numero, un titre et un fichier");
const derniere = A.CDC.decisions[A.CDC.decisions.length - 1].id;
vrai(hc.includes(derniere), "la dernière décision (" + derniere + ") est affichée");
const ouverte = A.CDC.questions.find(q => q.urgence !== "tranchee");
vrai(!!ouverte && hc.includes(ouverte.id),
     "une question encore ouverte (" + (ouverte && ouverte.id) + ") est affichée");
vrai(!hc.includes(">Q44<"), "une question tranchée ne figure plus dans les ouvertes");
vrai(hc.includes(A.CDC.genere), "la page date son index");
A.Controllers.Pages.ouvrir("features");
const hf = p.doc.getElementById("detail").innerHTML;
const nFeat = A.Views.Pages.FEATURES.reduce((s, [, l]) => s + l.length, 0);
vrai(nFeat >= 40, nFeat + " fonctionnalités listées");
vrai(hf.includes("V4"), "les jalons y figurent");
vrai(hf.includes("Moteur de filtres"), "le moteur de filtres (D74) est listé");
vrai(hf.includes("DMARC"), "la délivrabilité DMARC est listée");
vrai(hf.includes("expéditeur externe"), "l'affichage sûr est listé");
A.Controllers.Pages.ouvrir("roadmap");
eq(A.Views.Pages.ROADMAP.length, 5, "cinq jalons dans la feuille de route");
vrai(p.doc.getElementById("detail").innerHTML.includes("jalon v5"),
     "le jalon V5 a son propre style");

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
