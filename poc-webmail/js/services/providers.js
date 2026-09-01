/* CAPACITÉS ENFICHABLES — tâches, contacts, fichiers, calendrier.

   Chacune est un CONTRAT, et non une fonctionnalité d'AtomBox. Le même écran,
   le même geste, la même trace d'appel — seul le fournisseur change :

     natif       AtomBox tient la donnée lui-même (une table, une requête)
     connecteur  Dolibarr, Redmine, Nextcloud… tiennent la donnée, AtomBox appelle

   Le NATIF N'EST PAS UN REPLI : c'est le produit vendu seul. AtomBox se propose
   aussi comme une SUITE COLLABORATIVE CENTRÉE SUR LA MESSAGERIE — et dans cette
   lecture, tâches, contacts, fichiers et calendrier ne sont pas des accessoires,
   ce sont les quatre choses qui naissent d'un email. Le pivot est le message :
   là où Nextcloud part du fichier et un ERP du client, AtomBox part de l'échange.

   Les connecteurs servent l'autre cas : s'insérer chez quelqu'un qui vit déjà
   dans Dolibarr ou Nextcloud, sans dupliquer ses données. Les deux positions
   doivent être tenables sans réécrire une ligne d'interface — c'est exactement
   ce que ce registre vérifie.

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
        natif:     { label:"AtomBox (natif)", ic:"⚛", table:"tache",
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
        natif:     { label:"AtomBox (natif)", ic:"⚛", table:"correspondant",
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
        natif:     { label:"AtomBox (magasin d'octets)", ic:"⚛", table:"piece_jointe",
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
        natif:     { label:"AtomBox (natif)", ic:"⚛", table:"evenement",
                     note:"suffisant pour des échéances de traitement ; insuffisant pour un " +
                          "agenda partagé, qui demande la disponibilité et les invitations" },
        caldav:    { label:"CalDAV (Nextcloud)", ic:"☁", base:"nextcloud-mmi",
                     endpoint:"/remote.php/dav/calendars/{user}/",
                     note:"le bon choix dès qu'un humain doit voir l'échéance dans son agenda " +
                          "habituel plutôt que dans un webmail" },
      } },
  };

  /* Défaut : TOUT natif — la suite autonome. C'est la configuration à laquelle il
     faut que le produit soit bon, pas celle où il se contente de brancher.

     V1 : des outils LÉGERS. Une tâche avec un titre, une échéance et un statut ;
     un contact qui est le correspondant qu'on a déjà ; un fichier qui est la pièce
     jointe qu'on stocke déjà ; un calendrier qui porte des échéances. Rien de plus.
     Ce qui est léger et cohérent bat ce qui est complet et à moitié fait — et pour
     ceux qui veulent complet, les connecteurs existent dès la V1. */
  const DEFAUT = { taches:"natif", contacts:"natif", fichiers:"natif", calendrier:"natif" };

  const Providers = {
    CAPACITES,
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
