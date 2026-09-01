/* CAPACITÉS ENFICHABLES — tâches, contacts, fichiers, calendrier.

   Chacune est un CONTRAT, et non une fonctionnalité d'AtomBox. Le même écran,
   le même geste, la même trace d'appel — seul le fournisseur change :

     natif       AtomBox tient la donnée lui-même (une table, une requête)
     connecteur  Dolibarr, Redmine, Nextcloud… tiennent la donnée, AtomBox appelle

   Le NATIF N'EST PAS UN REPLI : c'est le produit vendu seul. AtomBox se propose
   aussi comme une SUITE COLLABORATIVE CENTRÉE SUR LA MESSAGERIE — contacts,
   tâches, cloud et CRM ne sont pas des accessoires, ce sont les choses qui
   naissent d'un email. Le pivot est le message : là où Nextcloud part du fichier
   et un ERP du client, AtomBox part de l'échange.

   MAIS PAS TOUT DE SUITE. Les composants internes sont une CIBLE DE V3. En V1 et
   V2, AtomBox est une messagerie qui SE BRANCHE : les capacités passent par des
   connecteurs, ou ne sont pas là. Écrire un CRM interne pendant qu'on écrit un
   moteur de stockage, c'est rater les deux — et un connecteur Dolibarr rend le
   service dès la V1, chez le seul type de client qu'on ait.

   Ce que ce registre garantit, c'est que la V3 ne demandera aucune réécriture
   d'interface : le contrat est posé maintenant, les implémentations natives
   viendront s'y brancher comme les autres.

   C'est le prolongement direct de D21 (« conf déclarative + module natif côté
   application ») : ce qui est déclaratif ici, c'est le CHOIX du fournisseur, pas
   la façon de l'appeler.

   La liste ci-dessous n'est pas fermée : ajouter un fournisseur, c'est ajouter
   une entrée et une implémentation du contrat — jamais toucher à un écran.

   Ce que le POC démontre : l'écran ne sait pas lequel est branché. S'il le
   savait, ajouter un fournisseur voudrait dire rouvrir l'interface. */
(function (ABX) {
  "use strict";

  const CAPACITES = {
    taches: {
      label: "Gestionnaire de tâches", ic: "☑",
      contrat: ["creer(titre, echeance, message_id)", "lister(filtre)", "cloturer(id)"],
      fournisseurs: {
        aucun:     { label:"Aucun", ic:"—", absent:true, v:1,
                     note:"la capacité n'existe pas : l'entrée de menu disparaît. C'est un état " +
                          "normal en V1, pas une panne — mieux vaut pas de tâches qu'un " +
                          "gestionnaire de tâches à moitié fait" },
        natif:     { label:"AtomBox (natif)", ic:"⚛", table:"tache", v:3,
                     note:"une table de plus, aucun appel réseau — et le lien avec le message " +
                          "est une clé étrangère, pas une URL qui peut mourir" },
        dolibarr:  { label:"Dolibarr — projets/tâches", ic:"🏢", base:"dolibarr-mmi",
                     endpoint:"/api/index.php/tasks",
                     note:"la tâche vit là où sont le client, le devis et le temps passé ; " +
                          "AtomBox ne stocke qu'une référence" },
        redmine:   { label:"Redmine — demandes", ic:"🛟", base:"redmine-ipro",
                     endpoint:"/issues.json",
                     note:"adapté au support : la demande a déjà un cycle de vie, des versions " +
                          "et un suivi de temps" },
        nextcloud: { label:"Nextcloud Deck / Tasks", ic:"☁", base:"nextcloud-mmi",
                     endpoint:"/remote.php/dav/calendars/{user}/tasks/",
                     note:"CalDAV VTODO : interopérable avec les clients mobiles, mais aucun " +
                          "lien métier — la tâche ne saura pas ce qu'est un client" },
      } },
    contacts: {
      label: "Gestionnaire de contacts", ic: "👤",
      contrat: ["chercher(adresse)", "fiche(id)", "creer(nom, adresses[])"],
      fournisseurs: {
        aucun:     { label:"Aucun", ic:"—", absent:true, v:1,
                     note:"aucune fiche : le correspondant reste un nom et une adresse dans le " +
                          "message, ce qui suffit à beaucoup d'usages" },
        natif:     { label:"AtomBox — lecture (V1) / carnet (V3)", ic:"⚛", table:"correspondant", v:1,
                     note:"la table correspondant existe DÉJÀ (D35) : le contact natif n'est " +
                          "pas une fonctionnalité de plus, c'est l'affichage de ce qu'on a" },
        carddav:   { label:"CardDAV (Nextcloud)", ic:"☁", base:"nextcloud-mmi",
                     endpoint:"/remote.php/dav/addressbooks/users/{user}/contacts/",
                     note:"le carnet suit l'utilisateur sur son téléphone ; en contrepartie, " +
                          "l'identité multi-adresses de D35 doit être reconstruite à chaque appel" },
        dolibarr:  { label:"Dolibarr — contacts/tiers", ic:"🏢", base:"dolibarr-mmi",
                     endpoint:"/api/index.php/contacts",
                     note:"le contact EST le tiers : c'est le seul fournisseur qui donne " +
                          "l'encours et les pièces avec la fiche" },
        ldap:      { label:"Annuaire LDAP", ic:"🗂", base:"ldap-interne",
                     endpoint:"ldap://annuaire/ou=people,dc=…",
                     note:"l'annuaire d'entreprise : autorité sur les collaborateurs, muet sur " +
                          "les tiers — souvent à combiner avec un second fournisseur" },
      } },
    fichiers: {
      label: "Gestionnaire de fichiers", ic: "📁",
      contrat: ["deposer(blob, chemin)", "chercher(nom)", "lien(id)"],
      fournisseurs: {
        aucun:     { label:"Aucun", ic:"—", absent:true, v:1,
                     note:"les pièces jointes restent dans les messages — elles y sont déjà " +
                          "stockées, cherchables et dédupliquées. « Aucun » ne veut pas dire " +
                          "« rien » : cela veut dire pas de second classement" },
        natif:     { label:"AtomBox — cloud (V3)", ic:"⚛", table:"fichier", v:3,
                     note:"le fichier est DÉJÀ stocké et dédupliqué (D24) : « enregistrer » ne " +
                          "copie rien, cela pose un nom et un classement sur un octet existant" },
        nextcloud: { label:"Nextcloud (WebDAV)", ic:"☁", base:"nextcloud-mmi",
                     endpoint:"/remote.php/dav/files/{user}/",
                     note:"⚠ dépose une COPIE : l'octet existe alors deux fois, et la " +
                          "déduplication d'AtomBox ne protège plus rien de ce côté-là" },
      } },
    calendrier: {
      label: "Calendrier", ic: "📅",
      contrat: ["evenements(du, au)", "creer(titre, debut, fin, message_id)"],
      fournisseurs: {
        aucun:     { label:"Aucun", ic:"—", absent:true, v:1,
                     note:"les échéances restent dans le statut du message" },
        natif:     { label:"AtomBox (natif)", ic:"⚛", table:"evenement", v:3,
                     note:"suffisant pour des échéances de traitement ; insuffisant pour un " +
                          "agenda partagé, qui demande la disponibilité et les invitations" },
        caldav:    { label:"CalDAV (Nextcloud)", ic:"☁", base:"nextcloud-mmi",
                     endpoint:"/remote.php/dav/calendars/{user}/",
                     note:"le bon choix dès qu'un humain doit voir l'échéance dans son agenda " +
                          "habituel plutôt que dans un webmail" },
      } },
    crm: {
      label: "CRM — affaires et opportunités", ic: "📈",
      contrat: ["affaires(correspondant)", "creer(titre, montant, correspondant)", "avancer(id, etape)"],
      fournisseurs: {
        aucun:     { label:"Aucun", ic:"—", absent:true, v:1,
                     note:"les tags client / fournisseur suffisent à classer ; le suivi d'affaire " +
                          "se fait ailleurs" },
        natif:     { label:"AtomBox — CRM (V3)", ic:"⚛", table:"affaire", v:3,
                     note:"le CRM natif est le composant le plus ambitieux de la V3 : c'est celui " +
                          "qui transforme un webmail en outil de travail — et celui qui a le plus " +
                          "de concurrents établis" },
        dolibarr:  { label:"Dolibarr — projets/opportunités", ic:"🏢", base:"dolibarr-mmi",
                     endpoint:"/api/index.php/projects", v:1,
                     note:"le CRM est déjà là, avec le tiers, le devis et la facture : AtomBox " +
                          "n'a qu'à poser le tag et afficher le contexte (D03)" },
      } },
  };

  /* LES CANAUX — au-delà de l'email, en V4.
     Ce ne sont pas des capacités enfichables : c'est de l'INGESTION, donc le cœur
     du moteur. Ils sont listés ici pour une seule raison — ce qu'il faut ne PAS
     s'interdire dès la V1 (voir l'écran d'administration, volet « Canaux »). */
  const CANAUX = [
    { id:"email",    label:"E-mail",     ic:"✉",  v:1, etat:"le produit" },
    { id:"interne",  label:"Messagerie interne", ic:"💬", v:2, etat:"hors SMTP (D12)" },
    { id:"sms",      label:"SMS",        ic:"📱", v:4, etat:"passerelle opérateur" },
    { id:"whatsapp", label:"WhatsApp",   ic:"🟢", v:4, etat:"API Business" },
    { id:"tel",      label:"Téléphonie", ic:"📞", v:4, etat:"CTI / journal d'appels + enregistrements" },
  ];

  /* Défaut : ce qui est DISPONIBLE EN V1, c'est-à-dire des connecteurs — sauf les
     contacts, dont la lecture est gratuite puisque `correspondant` existe déjà
     pour le rattachement (D35). Une capacité sans connecteur configuré n'est pas
     dégradée : elle est ABSENTE, et son entrée de menu disparaît. */
  const DEFAUT = { taches:"dolibarr", contacts:"natif", fichiers:"aucun",
                   calendrier:"caldav", crm:"dolibarr" };

  const Providers = {
    CAPACITES, CANAUX,
    choix: { ...DEFAUT },

    charge(sauve) { if (sauve) Object.assign(Providers.choix, sauve); },

    actif(cap) {
      const c = CAPACITES[cap];
      const id = Providers.choix[cap] || DEFAUT[cap];
      return { cap, id, ...c.fournisseurs[id], capacite: c };
    },
    natif: cap => Providers.actif(cap).id === "natif",

    choisir(cap, id) {
      if (!CAPACITES[cap] || !CAPACITES[cap].fournisseurs[id]) return;
      const f = CAPACITES[cap].fournisseurs[id];
      if (f.v > 1) ABX.log({ label:"« " + f.label + " » — aperçu, prévu en V" + f.v, etapes:[
        { t:"note", label:"pas livrable à ce jalon",
          detail:"les composants internes de la suite sont une cible de V3 ; les canaux " +
                 "non-mail, de V4",
          index:"le POC bascule quand même : voir les deux cascades côte à côte est le seul " +
                "moyen de juger ce que le natif apporterait. Le contrat est posé maintenant " +
                "pour que la V3 s'y branche sans réécrire une ligne d'interface" },
      ]});
      const avant = Providers.actif(cap);
      Providers.choix[cap] = id;
      ABX.Store.ui.providers = { ...Providers.choix };
      ABX.Store.save();
      const apres = Providers.actif(cap);
      ABX.log({ label: "Fournisseur « " + CAPACITES[cap].label + " » : " +
                       avant.label + " → " + apres.label, etapes: [
        { t:"ui", label:"choix dans l'administration",
          detail:"views/admin.js → Providers.choisir('" + cap + "', '" + id + "')" },
        { t:"sql", label:"la configuration est en base, pas dans un fichier",
          detail:
`UPDATE configuration SET valeur = :fournisseur
 WHERE organisation_id = :org AND cle = 'capacite.` + cap + `';`,
          index:"changer de fournisseur ne doit pas demander un redéploiement (D21) — et doit " +
                "être tracé : une bascule change ce que les utilisateurs voient" },
        { t:"note", label:"ce que la bascule ne fait PAS",
          detail:"aucune migration des données déjà créées chez l'ancien fournisseur",
          index:"⚠ les tâches créées dans Dolibarr restent dans Dolibarr. Une bascule est un " +
                "changement de destination, pas un déménagement — à dire à l'utilisateur, " +
                "sinon il croira avoir perdu son travail",
          warn:true },
        { t:"render", label:"les écrans ne changent pas",
          detail:"aucune vue à modifier : c'est tout l'intérêt du contrat",
          index:"si l'écran avait dû changer, le contrat serait mal posé" },
      ]});
      ABX.Bus.emit("corpus:changed", {});
    },
  };

  ABX.Providers = Providers;
})(window.ABX = window.ABX || {});
