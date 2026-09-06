/* SURCOUCHE « AIDE » — le contenu des points de contexte pour l'UTILISATEUR (D142).

   Un point de contexte est un endroit de l'interface où quelque chose
   s'explique. Ce fichier est chargé en POC ET en prod : c'est la voix de
   l'aide. Le fichier jumeau contexte.cdc.js (POC seulement) dit, au même
   point, ce que le CDC en dit. Les deux s'écrivent ensemble : celui qui
   rédige l'aide a la décision sous les yeux.

   Règle d'écriture : parler à quelqu'un qui n'a pas lu le CDC. Jamais un
   numéro de décision, jamais une règle du catalogue par son code. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt;
  R.modes.push("aide");
  const A = (point, fn) => R.defineFor("contexte." + point, "aide", fn);

  A("fiabilite.valide", () => `<div class="hint">Quelqu'un de votre équipe a marqué cette
    adresse comme fiable, et ce message est bien authentifié par son domaine. Cette confiance
    s'éteint d'elle-même si l'expéditeur change d'habitudes ou si son domaine cesse d'être
    vérifiable.</div>`);
  A("fiabilite.non_aligne", ({ m }) => `<div class="hint">Rien ne prouve que ce message vienne
    réellement de cette adresse${m && m.connu ? " — même si vous la connaissez" : ""}. Aucun
    indicateur de confiance ne peut donc s'afficher, et on ne peut pas la marquer fiable depuis
    ce message.</div>`);
  A("fiabilite.connu", () => `<div class="hint">Vous pouvez marquer cette adresse comme fiable.
    Par défaut, cela vaut pour cette boîte ; un gestionnaire peut l'étendre à tout le domaine.</div>`);
  A("reponse.refus", ({ m }) => `<div class="hint">Une réponse envoyée${m && m.dsn ? " il y a " + m.dsn.jours + " jours" : ""}
    à cette adresse a été rejetée par le serveur destinataire. Le refus est daté et sera
    réévalué : une adresse peut redevenir joignable.</div>`);
  A("reponse.diffusion", () => `<div class="hint">C'est un message de diffusion : l'expéditeur
    ne lit pas les réponses. L'action utile est « se désabonner ».</div>`);
  A("reponse.notification", () => `<div class="hint">C'est une notification automatique — elle
    reste dans votre file de travail parce qu'elle peut attendre quelque chose de vous.</div>`);
  A("usurpation", ({ m }) => `<div class="hint">Le nom affiché correspond à un contact que vous
    connaissez, mais l'adresse n'est pas la sienne. AtomBox vous avertit ; il ne rejette pas le
    message — à vous de juger.</div>`);
  A("transfert.reference", ({ src }) => `<div class="hint">Ce message a été transféré sans être
    copié : il pointe l'original${src ? "" : ", qui n'existe plus"}.</div>`);
  A("statut", () => `<div class="hint">Le statut dit où en est le traitement de ce message ;
    « traité » le sort de votre file de travail.</div>`);
  A("nav.v0", () => `<div class="hint">Les dossiers sont ceux de votre messagerie IMAP ; ce que
    vous y faites est synchronisé avec vos autres clients.</div>`);
  A("liste.expediteur.inconnu", () => `<div class="hint">Expéditeur inconnu : l'adresse est
    affichée en premier, le nom déclaré ensuite — le nom, lui, n'est pas vérifié.</div>`);

  ABX.ContexteAide = { points: R.pointsDuMode("aide") };
  A("connexion", () => `<div class="hint">Vos identifiants AtomBox — ceux de votre compte, pas ceux
    d'une boîte. Si votre organisation utilise une connexion unique, c'est elle qui s'ouvre.</div>`);
  A("nav.virtuel", () => `<div class="hint">Un dossier virtuel est un filtre : un message y
    apparaît s'il porte <b>tous</b> les tags choisis. Une valeur laissée vide prend toute la
    famille. Le supprimer n'efface aucun message.</div>`);
  A("nav.epingle", () => `<div class="hint">Les dossiers épinglés restent en tête, dans
    l'ordre où vous les avez épinglés. Ils sont aussi à leur place habituelle. C'est un réglage
    personnel : il ne change rien pour vos collègues.</div>`);

})(window.ABX = window.ABX || {});
