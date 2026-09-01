/* FIXTURES — la CARDINALITÉ est le sujet, pas le volume (D80).
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

  /* Les six familles de D76 : un AXE, ses VALEURS. */
  const AXES = [
    { id:"fournisseur",  label:"Fournisseurs",    icon:"📦", n:200 },
    { id:"client",       label:"Clients",         icon:"🏢", n:52,  sub:"en cours" },
    { id:"partenaire",   label:"Partenaires",     icon:"🤝", n:14 },
    { id:"collaborateur",label:"Collaborateurs",  icon:"👥", n:11 },
    { id:"sav",          label:"SAV",             icon:"🛟", n:23,  ticket:true },
    { id:"notification", label:"Notifications",   icon:"🔔", n:6,
      fixed:["Urgences","Debug","Monitoring","Sauvegardes","CI/CD","Sécurité"] },
    { id:"social",       label:"Réseaux sociaux", icon:"💬", n:5,
      fixed:["LinkedIn","Facebook","Instagram","X","YouTube"] },
  ];

  const valeurs = {};
  AXES.forEach(a => {
    valeurs[a.id] = [];
    const n = a.fixed ? a.fixed.length : a.n;
    for (let i = 0; i < n; i++) {
      const label = a.fixed ? a.fixed[i]
                  : a.id === "collaborateur" ? pers()
                  : a.ticket ? "Ticket #" + (4200 + i * 7)
                  : nom();
      valeurs[a.id].push({
        id: a.id + ":" + F.slug(label), label, axe: a.id,
        poids: a.id === "notification" ? P.int(20, 60) : P.int(4, 26),
        actif: P.next() < .45,        // « clients en cours »
        last: 0,                      // renseigné après génération du corpus
      });
    }
  });

  /* Dossiers spéciaux. « Traités » et « Archives » sont des VUES sur
     motif_sortie, pas des dossiers : c'est D30 lu par D51. */
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

  const SUJETS = ["Devis {n}","Facture {n}","Relance facture {n}","Commande {n} expédiée",
    "Re: Commande {n}","Bon de livraison {n}","Contrat de maintenance","Demande d'information",
    "Réclamation client","Planning d'intervention","Avoir {n}","Confirmation de rendez-vous"];
  const CORPS = [
    "Bonjour,\n\nComme convenu lors de notre échange, vous trouverez ci-joint les éléments demandés.\n\nBien cordialement,",
    "Bonjour,\n\nNous accusons réception de votre demande. Un retour vous sera fait sous 48 heures.\n\nCordialement,",
    "Bonjour,\n\nPourriez-vous nous confirmer les quantités avant expédition ?\n\nMerci d'avance,",
    "Bonjour,\n\nLe document est en pièce jointe. N'hésitez pas si vous avez des questions.\n\nBien à vous,"];

  /* Le compte connecté et ses boîtes — l'identité d'envoi est celle d'une BOÎTE (Q26). */
  const MOI = { nom:"Mathieu Moulin", boites: [
    { id:"b1", adresse:"mathieu@iprospective.eu",   label:"Perso" },
    { id:"b2", adresse:"contact@iprospective.eu",   label:"Boîte commune" },
    { id:"b3", adresse:"commandes@iprospective.eu", label:"Commandes" },
  ]};
  const interne = a => /@iprospective\.(eu|fr)$/i.test((a || "").trim());

  ABX.Fixtures = { AXES, valeurs, SPECIAUX, UTIL, SUJETS, CORPS, MOI, interne, nom, pers,
                   estAxe: id => AXES.some(a => a.id === id) };
})(window.ABX = window.ABX || {});
