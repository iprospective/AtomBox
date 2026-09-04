/* SURCOUCHE « CDC » — le contenu des points de contexte pour QUI CONÇOIT (D142).

   POC seulement : ce fichier n'est pas chargé par index.prod.html. Au même
   point que contexte.aide.js, il dit ce que le CDC en dit — la décision, la
   règle du catalogue, ce qu'on refuse de faire et pourquoi. Les identifiants
   D/Q/C y sont cliquables (markdown.js) et ouvrent leur section.

   C'est le seul fichier où un numéro de décision a le droit d'apparaître dans
   une vue : le harnais vérifie qu'en mode produit aucun « D1xx » ne subsiste. */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt, M = ABX.Markdown;
  R.modes.push("cdc");
  const Cd = (point, fn) => R.defineFor("contexte." + point, "cdc", ctx => `<div class="hint cdc">${fn(ctx)}</div>`);
  const md = t => M ? M.inline(t) : F.esc(t);

  Cd("fiabilite.valide", () => md("**D137** — la validation ne fait pas taire les règles fortes du catalogue (**D128**) : elle atténue les indices faibles, elle n'ouvre pas de porte. Elle s'éteint sur rupture d'habitude (B3) ou si le domaine cesse d'être authentifiable."));
  Cd("fiabilite.non_aligne", ({ m }) => md("**D137** — aucun indicateur sans alignement DMARC de *ce* message : marquer fiable un identifiant usurpable désigne la cible à l'attaquant." + (m && m.connu ? " L'expéditeur est au carnet — c'est exactement le cas où un affichage rassurant serait une faute." : "")));
  Cd("fiabilite.connu", () => md("**D137** / **D106** — la validation a une portée : boîte par défaut, domaine pour un gestionnaire. Sur boîte partagée, c'est un acte collectif, tracé (**D054**)."));
  Cd("reponse.refus", () => md("**D131** / **D119** — on refuse sur un **fait** (un DSN 5xx corrélé par VERP), jamais sur le mot « noreply ». La marque est datée et se réévalue (**D127**)."));
  Cd("reponse.diffusion", () => md("**D130** / **D132** — nature `liste` : hors de la file des non traités ; désabonnement jamais automatique (un lien suivi sans geste est un confirmateur d'adresse)."));
  Cd("reponse.notification", () => md("**D130** — nature `notification` : *entre* dans la file. Une facture est une machine qui attend un paiement ; un booléen « automatique » l'aurait cachée."));
  Cd("usurpation", ({ m }) => md("**D128** règle **B1** — le meilleur signal du catalogue, et le seul qu'un anti-spam générique ne peut pas produire." + (m && /iprospect/.test((m.mail || "").split("@")[1] || "") ? " S'y ajoute **A8** : domaine sosie." : "") + " On alerte, on ne rejette pas (**D139** : un score ne refuse jamais)."));
  Cd("transfert.reference", () => md("**D058** / **D067** — transfert par référence, sans copie ; le pointeur peut mourir (**Q030**)."));
  Cd("statut", () => md("**D093** — un statut *pilote*, un tag *classe*. « Traité » = `sorti_le` + `motif_sortie` (**D014**), la clé d'archivage."));
  Cd("nav.v0", () => md("**D140b** — dossiers IMAP ingérés comme tags d'origine (**D046**), états synchronisés avec IMAP qui reste la vérité jusqu'à la V2."));
  Cd("liste.expediteur.inconnu", () => md("**D126** — le nom affiché n'est pas une identité : l'adresse en premier pour un inconnu. **D128** B1 quand le nom est connu et l'adresse non."));

  ABX.ContexteCdc = { points: R.pointsDuMode("cdc") };
})(window.ABX = window.ABX || {});
