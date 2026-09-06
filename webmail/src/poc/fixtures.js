/* FIXTURES — la CARDINALITÉ est le sujet, pas le volume (D080).
   200 fournisseurs dans un panneau latéral : c'est cette échelle qui décide de
   la conception de l'écran, et elle ne se devine pas sur vingt dossiers. */
(function (ABX) {
  "use strict";
  const P = ABX.PRNG, F = ABX.Fmt;

  const MOTS = ["Acme","Belair","Cardin","Delmas","Estève","Fabre","Garnier","Hublot","Imperia",
    "Jourdan","Klein","Lamotte","Moreau","Naudin","Orsini","Payet","Quintin","Roussel","Sablé",
    "Tessier","Ubald","Vernet","Wagner","Xavier","Yvelin","Zamora","Nord","Sud","Atlantique",
    "Provence","Rhône","Loire","Vallée","Bocage","Colline","Rivage","Plateau","Comptoir","Maison"];
  const SUFF = ["SARL","SAS","& Fils","Industries","Services","Distribution","Négoce","Conseil","Group","Atelier"];
  const PRENOMS = ["Marie","Jean","Sophie","Luc","Camille","Thomas","Julie","Pierre","Claire","Nicolas",
    "Anne","David","Laure","Marc","Émilie","Paul","Nadia","Hugo","Sarah","Vincent"];
  const NOMS = ["Durand","Martin","Bernard","Petit","Robert","Richard","Dubois","Moreau","Laurent","Simon"];

  const nom  = () => P.pick(MOTS) + " " + P.pick(SUFF);
  const pers = () => P.pick(PRENOMS) + " " + P.pick(NOMS);

  /* De quoi parlent les tickets de développement — sans quoi l'arborescence dirait
     « Devis 4271 » sous un ticket, ce qui ne trompe personne. */
  const TITRES_RM = ["moteur de filtres","import mbox","refonte du parseur MIME",
    "quarantaine spam","file d'envoi","corrélation des DSN","collecte DMARC",
    "déduplication des PJ","recherche plein texte","arborescence engendrée",
    "cascade de paramétrage","déchetterie","groupes internes","anti-usurpation",
    "SDK PHP","composant embarquable","export PDF","position de lecture"];

  /* Les six familles de D076 : un AXE, ses VALEURS. */
  const AXES = [
    { id:"fournisseur",  label:"Fournisseurs",    icon:"📦", n:200 },
    { id:"client",       label:"Clients",         icon:"🏢", n:52,  sub:"en cours" },
    { id:"partenaire",   label:"Partenaires",     icon:"🤝", n:14 },
    { id:"collaborateur",label:"Collaborateurs",  icon:"👥", n:11 },
    { id:"prospect",     label:"Prospects",       icon:"🎯", n:8,  poids:[2, 8] },
    { id:"sav",          label:"SAV",             icon:"🛟", n:23,  ticket:true },
    /* Un axe poussé par une AUTRE application que l'ERP (D019/D020) : Redmine tient
       les tickets, Dolibarr les clients. Deux applications, deux axes, deux ACL —
       et la même arborescence engendrée (D077). */
    { id:"developpement",label:"Développement",   icon:"🧩", n:34,  rm:true,
      app:"redmine-ipro" },
    /* Trois axes calés sur l'arborescence IMAP réelle (chapitre 14) : le nombre
       de messages de chacun approche celui mesuré en production — 116 pour
       l'administratif, 498 pour les demandes, 29 pour les listes. */
    { id:"contact",      label:"Demandes et contact", icon:"📨", n:4, poids:[80, 150],
      fixed:["Formulaire du site","Contact général","Demande de devis","Webmaster"] },
    { id:"administratif",label:"Administratif",   icon:"🏛", n:7, poids:[8, 26],
      fixed:["URSSAF","Impôts","Greffe du tribunal","Banque","Assurance",
             "Retraite","Mutuelle"] },
    /* Une liste de discussion EST une diffusion : cet axe alimente donc aussi la
       branche Abonnements (D130, D133), sans qu'on ait rien à déclarer. */
    { id:"forum",        label:"Forums et listes",icon:"💡", n:5, poids:[3, 9],
      fixed:["Dolibarr","PostgreSQL","Debian","Dovecot","Symfony"] },
    { id:"notification", label:"Notifications",   icon:"🔔", n:6,
      fixed:["Urgences","Debug","Monitoring","Sauvegardes","CI/CD","Sécurité"] },
    { id:"social",       label:"Réseaux sociaux", icon:"💬", n:5,
      fixed:["LinkedIn","Facebook","Instagram","X","YouTube"] },
    /* Un axe DÉRIVÉ (D133) : ses dossiers ne sont pas des tiers, ils sont
       CALCULÉS depuis le corpus — un par liste de diffusion rencontrée. Rien
       n'est fabriqué pour lui : les messages qu'il montre vivent déjà dans
       l'axe de leur correspondant, et ils n'ont pas bougé (D077). */
    { id:"abonnement",   label:"Abonnements",     icon:"📰", n:0, derive:true },
  ];

  const valeurs = {};
  AXES.forEach(a => {
    valeurs[a.id] = [];
    const n = a.derive ? 0 : a.fixed ? a.fixed.length : a.n;
    for (let i = 0; i < n; i++) {
      const label = a.fixed ? a.fixed[i]
                  : a.id === "collaborateur" ? pers()
                  : a.ticket ? "Ticket #" + (4200 + i * 7)
                  : a.rm ? "RM" + (2830 + i * 3) + " · " + P.pick(TITRES_RM)
                  : nom();
      valeurs[a.id].push({
        id: a.id + ":" + F.slug(label), label, axe: a.id,
        poids: a.poids ? P.int(a.poids[0], a.poids[1])
             : a.id === "notification" ? P.int(20, 60) : P.int(4, 26),
        actif: P.next() < .45,        // « clients en cours »
        last: 0,                      // renseigné après génération du corpus
      });
    }
  });

  /* LE WORKFLOW DE TRAITEMENT — un statut, pas un tag.
     Un tag CLASSE : il est ouvert, interopérable, partagé entre applications,
     soumis à une ACL d'axe. Un statut PILOTE : il est ordonné, fermé, propre au
     compte, et c'est lui qui décide de ce qui reste à faire. Les confondre, c'est
     se retrouver avec « à faire » dans le même espace de noms que « Belair SAS »,
     et une application connectée capable de vider votre file de travail.

     `lu_le` reste à part : c'est un FAIT daté (D041), pas un état — un message peut
     être lu et à faire, non lu et déjà pris en charge par un collègue. */
  const STATUTS = [
    { id:"nouveau",  label:"Nouveau",    ic:"○", ordre:0 },
    { id:"a_faire",  label:"À faire",    ic:"◔", ordre:1 },
    { id:"en_cours", label:"En cours",   ic:"◑", ordre:2 },
    { id:"attente",  label:"En attente", ic:"◕", ordre:3, note:"relance attendue" },
    { id:"traite",   label:"Traité",     ic:"●", ordre:4, sortie:"traite" },
  ];
  const statut = id => STATUTS.find(s => s.id === id) || STATUTS[0];

  /* Dossiers spéciaux. « Traités » et « Archives » sont des VUES sur
     motif_sortie, pas des dossiers : c'est D030 lu par D051. */
  const SPECIAUX = [
    { id:"inbox",    label:"Boîte de réception", icon:"📥", poids:64 },
    { id:"sent",     label:"Envoyés",            icon:"📤", poids:22, sortant:true },
    { id:"drafts",   label:"Brouillons",         icon:"📝", poids:0 },
    { id:"junk",     label:"Indésirables",       icon:"🚫", poids:18 },
    { id:"trash",    label:"Corbeille",          icon:"🗑", poids:0 },
    { id:"traites",  label:"Traités",            icon:"✓",  poids:0, vue:true },
    { id:"archives", label:"Archives",           icon:"🗄", poids:0, vue:true },
  ];
  const UTIL = [
    { id:"u:devis",     label:"Devis en attente", icon:"📁", poids:11 },
    { id:"u:rh",        label:"RH",               icon:"📁", poids:9 },
    { id:"u:juridique", label:"Juridique",        icon:"📁", poids:7 },
  ];

  const SUJETS_RM = ["Re: {t}","{t} — relecture demandée","[RM{n}] nouvelle note",
    "{t} : question de conception","{t} — MR prête à relire","[RM{n}] passage en recette",
    "{t} : régression constatée","{t} — chiffrage à valider","[RM{n}] livré, à tester"];
  const SUJETS = ["Devis {n}","Facture {n}","Relance facture {n}","Commande {n} expédiée",
    "Re: Commande {n}","Bon de livraison {n}","Contrat de maintenance","Demande d'information",
    "Réclamation client","Planning d'intervention","Avoir {n}","Confirmation de rendez-vous"];
  /* Un dossier « URSSAF » qui parle de bons de livraison trahit la maquette :
     le sujet suit l'axe, comme pour les tickets de développement. */
  const SUJETS_AXE = {
    administratif: ["Déclaration trimestrielle","Avis d'échéance","Attestation de vigilance",
      "Relevé annuel de situation","Appel de cotisation {n}","Accusé de dépôt"],
    contact: ["Nouvelle entrée : Contact","Demande d'information via le site",
      "Demande de devis","Question sur vos prestations","Rappel demandé"],
    forum: ["[{v}] Re: problème de configuration","[{v}] Annonce de version",
      "[{v}] Re: retour d'expérience","[{v}] Question de débutant"],
    prospect: ["Suite à notre échange","Présentation de nos services",
      "Demande de rendez-vous","Relance — proposition {n}"],
  };
  const CORPS = [
    "Bonjour,\n\nComme convenu lors de notre échange, vous trouverez ci-joint les éléments demandés.\n\nBien cordialement,",
    "Bonjour,\n\nNous accusons réception de votre demande. Un retour vous sera fait sous 48 heures.\n\nCordialement,",
    "Bonjour,\n\nPourriez-vous nous confirmer les quantités avant expédition ?\n\nMerci d'avance,",
    "Bonjour,\n\nLe document est en pièce jointe. N'hésitez pas si vous avez des questions.\n\nBien à vous,"];

  /* Le compte connecté et ses boîtes — l'identité d'envoi est celle d'une BOÎTE (Q026). */
  const MOI = { nom:"Mathieu Moulin", boites: [
    { id:"b1", adresse:"mathieu@iprospective.eu",   label:"Perso" },
    { id:"b2", adresse:"contact@iprospective.eu",   label:"Boîte commune" },
    { id:"b3", adresse:"commandes@iprospective.eu", label:"Commandes" },
  ]};
  const interne = a => /@iprospective\.(eu|fr)$/i.test((a || "").trim());

  /* Administration : ce qu'un exploitant doit pouvoir régler sans base de données. */
  const DOMAINES = [
    { nom:"iprospective.eu", role:"pilote", boites:3, alias:7, mx:"mx1.iprospective.fr",
      ingestion:"IMAP (lecture seule)", note:"domaine de test, D049" },
    { nom:"iprospective.fr", role:"recette", boites:9, alias:41, mx:"mx1.iprospective.fr",
      ingestion:"IMAP (lecture seule)", note:"production intacte, D050" },
  ];
  /* D128 (B1) — les domaines sur lesquels une usurpation par nom se pose : le nom
     d'un correspondant connu, une adresse qui ne lui appartient pas. Deux d'entre
     eux sont des SOSIES du domaine pilote (règle A8) — la lettre change, pas le
     coup d'œil. */
  const DOMAINES_LIBRES = ["gmail.com", "outlook.fr", "free.fr",
                           "iprospective-eu.com", "iprospectlve.eu"];
  const BOITES = [
    { adresse:"mathieu@iprospective.eu",   type:"personnelle", quota:"12 Go", acces:1, msg:1284 },
    { adresse:"contact@iprospective.eu",   type:"commune",     quota:"40 Go", acces:4, msg:8210 },
    { adresse:"commandes@iprospective.eu", type:"commune",     quota:"40 Go", acces:3, msg:5602 },
    { adresse:"info@iprospective.eu",      type:"alias",       cible:"contact@iprospective.eu" },
    { adresse:"sav@iprospective.eu",       type:"alias",       cible:"contact@iprospective.eu" },
  ];
  const APPLICATIONS = [
    { code:"dolibarr-mmi",  label:"Dolibarr — MMI Négoce", type:"dolibarr",
      axes:["client","fournisseur"], droits:"lire, écrire", portee:"3 boîtes",
      jeton:"abx_tk_7f3c…", vu:"il y a 4 min" },
    { code:"redmine-ipro",  label:"Redmine — support", type:"redmine",
      axes:["sav","projet","developpement"], droits:"lire, écrire",
      portee:"sav@iprospective.eu, dev@iprospective.eu",
      jeton:"abx_tk_91ba…", vu:"il y a 2 h" },
    { code:"nextcloud-mmi", label:"Nextcloud — partage", type:"nextcloud",
      axes:["partenaire"], droits:"lire", portee:"tout le domaine",
      jeton:"abx_tk_c40e…", vu:"il y a 3 j" },
  ];

  ABX.Fixtures = { AXES, valeurs, SPECIAUX, UTIL, SUJETS, CORPS, MOI, interne, nom, pers,
                   STATUTS, statut, DOMAINES, DOMAINES_LIBRES, BOITES, APPLICATIONS, SUJETS_RM,
                   SUJETS_AXE,
                   estAxe: id => AXES.some(a => a.id === id) };
})(window.ABX = window.ABX || {});
