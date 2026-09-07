/* VUE MESSAGE — l'onglet ouvert sur un message.
   La barre d'actions change selon l'état du message : un message à la corbeille
   ne s'archive pas, un message sorti de la file se remet en file (Q009). */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt, Fx = ABX.Fixtures, C = ABX.Corpus;

  ABX.Views = ABX.Views || {};
  ABX.Views.Message = {
    render(m, ui) {
      /* le fil est chargé par le contrôleur (Api.fil, promesse) et posé sur m._fil ;
         la vue ne calcule rien — elle rend ce qu'on lui a donné (D141) */
      const fil = (m._fil || []).slice(0, 4);
      return `
        <div class="backbar"><button data-vue="liste">‹ ${F.esc(ui.folder.label)}</button></div>
        <div class="dhead">
          <div class="dsubj">${F.esc(m.sujet)}</div>
          <div class="dmeta">${R.render("expediteur", { m, long: true })} ·
            ${new Date(m.date_recue).toLocaleString("fr-FR")} · reçu sur <b>${F.esc(m.boite)}</b>
            ${m.nb_pieces_jointes ? " · 📎 " + m.nb_pieces_jointes : ""}
            ${m.motif_sortie ? " · " + R.render("statut.chip", { m }) : ""}
            ${m.dossier === "trash" ? ` · <span class="tag">corbeille</span>` : ""}</div>
          <div class="dacts">
            <button class="hbtn${m.reponse_possible === "non" ? " off" : ""}" data-c="rep"
              ${m.reponse_possible === "non" ? `disabled title="Cette adresse a rejeté une réponse` +
                ` — voir le bandeau ci-dessous (D131)"` : ""}>↩ Répondre</button>
            <button class="hbtn${m.reponse_possible === "non" ? " off" : ""}" data-c="reptous"
              ${m.reponse_possible === "non" ? "disabled" : ""}>↩↩ Tous</button>
            <button class="hbtn" data-c="tr">➦ Transférer</button>
            ${ABX.Views.Message.statutHtml(m)}
            <button class="hbtn ic" data-x="${m.lu ? "nonLu" : "lire"}"
              title="${m.lu ? "Marquer non lu" : "Marquer lu"}">${m.lu ? "◻" : "◼"}</button>
            <span class="pousse"></span>
            <button class="hbtn ic" id="plus" title="Autres actions">⋯</button>
            ${(m.dossier || m.dossier_origine) === "trash"
              ? `<button class="hbtn ic" data-x="restaurer" title="Restaurer">↩</button>
                 <button class="hbtn ic dgr" data-x="supprimer" title="Supprimer définitivement">✕</button>`
              : `<button class="hbtn ic" data-x="${(m.dossier || m.dossier_origine) === "junk" ? "nonJunk" : "junk"}"
                   title="${(m.dossier || m.dossier_origine) === "junk"
                     ? "Ce n'est pas un indésirable" : "Marquer indésirable"}">${
                     (m.dossier || m.dossier_origine) === "junk" ? "✓" : "🚫"}</button>
                 <button class="hbtn ic dgr" data-x="corbeille"
                   title="Mettre à la corbeille">🗑</button>`}
          </div>
          ${ABX.Views.Message.menuHtml(m)}
        </div>
        ${m.sens === "out" ? R.render("message.envoi", { e: m._envoi }) : ""}
        ${ABX.Views.Message.fiabiliteHtml(m)}
        ${ABX.Views.Message.repondHtml(m)}
        ${ABX.Views.Message.spoofHtml(m)}
        ${ABX.Views.Message.lienHtml(m)}
        ${R.render("message.tags", { m })}
        ${R.render("erp.panel", { m })}
        ${R.render("attachment.list", { m })}
        <div class="box"><h4>Fil de discussion (${fil.length} messages)</h4>
          <div class="dmeta">thread_id matérialisé — D055</div></div>
        <div class="thread">${fil.map(x =>
          R.render("thread.item", { x, courant: x.id === m.id })).join("")}</div>`;
    },

    /* Le STATUT est l'action principale d'un message : ni un tag ni un dossier,
       c'est où en est son traitement. Un sélecteur, donc, et pas trois boutons —
       l'ordre des états compte, et il doit se voir. */
    statutHtml(m) {
      if (ABX.V0()) return "";          // V0 : pas de workflow, IMAP n'a que lu/drapeau (D140)
      if (m.motif_sortie === "archive") return `<span class="tag">archivé</span>
        <button class="hbtn" data-x="refile" title="Remettre dans la file">↺ Reprendre</button>`;
      return `<select class="statsel st-${F.esc(m.statut || "nouveau")}" id="stat"
          title="Statut de traitement">
        ${ABX.Ref.statuts.map(x => `<option value="${x.id}"${x.id === m.statut ? " selected" : ""}
          >${x.ic} ${F.esc(x.label)}</option>`).join("")}</select>${R.contexte("statut", { m })}`;
    },

    /* Le menu « ⋯ » : ce qui est utile mais rare, et ce qui appartient à une
       capacité enfichable plutôt qu'au message lui-même. Le nom du fournisseur
       branché y est visible — l'utilisateur doit savoir où part sa tâche. */
    menuHtml(m) {
      const cap = c => ABX.Providers.actif(c);
      return `<div class="menu" id="menu" hidden>
        <div class="mgrp">Ce message</div>
        <button data-m="orig">⤓ Télécharger le .eml original</button>
        <button data-m="archiver">🗄 Archiver sans traiter</button>
        <div class="mgrp">Déplacer vers</div>
        ${ABX.Ref.util.map(u => `<button data-move="${F.esc(u.id)}">${u.icon} ${F.esc(u.label)}</button>`).join("")}
        <button data-move="">↩ Retirer du dossier</button>
        <div class="mgrp">Suite collaborative</div>
        <button data-m="tache">${cap("taches").ic} Créer une tâche
          <span class="mprov">${F.esc(cap("taches").label)}</span></button>
        <button data-m="contact">${cap("contacts").ic} Fiche du correspondant
          <span class="mprov">${F.esc(cap("contacts").label)}</span></button>
        ${m.nb_pieces_jointes ? `<button data-m="fichiers">${cap("fichiers").ic} Enregistrer les pièces jointes
          <span class="mprov">${F.esc(cap("fichiers").label)}</span></button>` : ""}
      </div>`;
    },

    /* D131 — on ne bloque JAMAIS sur une convention de nommage. « avertir » se
       deduit de la nature ; « non » demande une preuve, et la seule qui existe
       est un retour de non-remise sur une reponse deja tentee (D119). Un bouton
       grise sans explication est percu comme une panne : le motif est dit, et
       date. Et on ne refuse pas sans proposer a QUI ecrire. */
    /* D137 — le bandeau dit CE QU'ON SAIT et QUI l'a dit, jamais « fiable » tout
       court : une confiance sans auteur ni date n'est pas vérifiable, et elle ne
       sait pas s'éteindre. Le geste de validation a une PORTÉE (D106) — valider
       depuis une boîte partagée engage les autres, donc c'est tracé (D054). */
    /* Les bandeaux du message ouvert affichent un FAIT — validé, non authentifié,
       rejeté le 12 mars, usurpé — et laissent l'EXPLICATION aux points de
       contexte (D142) : « aide » dit à l'utilisateur ce que ça veut dire, « cdc »
       dit au concepteur quelle décision le porte. Le même point, deux voix ;
       en prod la seconde n'est pas chargée. */
    fiabiliteHtml(m) {
      if (ABX.V0()) return "";
      /* null = aucun verdict (V0, relève IMAP : l'IP est perdue — D026) : aucun indicateur, ni
         rassurant ni alarmant (D137) ; le vrai serveur sert null, le POC un nombre */
      if (m.sens === "out" || m.fiabilite == null || !m.dom || m.usurpation) return "";
      if (m.fiabilite >= 2)
        return `<div class="lien fiab-bloc" style="margin:12px 16px">✓ <b>Expéditeur validé</b> —
          quelqu'un de chez vous a marqué cette adresse comme fiable, et ce message est
          authentifié par son domaine.${R.contexte("fiabilite.valide", { m })}</div>`;
      if (!m.dom.aligne)
        return `<div class="lien" style="margin:12px 16px">◌ <b>Ce message n'est pas authentifié
          par son domaine.</b>${R.contexte("fiabilite.non_aligne", { m })}
          <button class="hbtn" style="margin-top:6px" disabled
            title="On ne valide pas une adresse sur un message non authentifié">
            Marquer cet expéditeur comme fiable</button></div>`;
      return `<div class="lien" style="margin:12px 16px">· Expéditeur connu, message authentifié —
        <b>aucune validation humaine</b>.${R.contexte("fiabilite.connu", { m })}
        <button class="hbtn" style="margin-top:6px">Marquer cet expéditeur comme fiable</button></div>`;
    },

    repondHtml(m) {
      if (ABX.V0()) return "";
      if (!m.reponse_possible || m.reponse_possible === "oui") return "";
      const alt = m.contact_alternatif
        ? `<div class="hint">Plutôt que d'abandonner : <b>${F.esc(m.contact_alternatif.nom)}</b>
           &lt;${F.esc(m.contact_alternatif.from_adresse)}&gt; est à votre carnet, sur le même domaine —
           montré, jamais présélectionné.</div>` : "";
      if (m.reponse_possible === "non")
        return `<div class="alerte-bloc">⛔ <b>Cette adresse n'accepte pas les réponses.</b>
          <div class="hint">Une réponse envoyée il y a ${m.dsn.jours} jours à
            <b>${F.esc(m.from_adresse)}</b> a été rejetée : <code>${F.esc(m.dsn.code)}</code>.</div>
          ${R.contexte("reponse.refus", { m })}${alt}</div>`;
      return `<div class="lien" style="margin:12px 16px">✉ <b>${
        m.nature === "liste" ? "Message de diffusion" : "Notification automatique"}</b> —
        l'expéditeur déclare ne pas lire les réponses. Répondre reste possible ; ce n'est
        simplement plus l'action principale.
        ${R.contexte(m.nature === "liste" ? "reponse.diffusion" : "reponse.notification", { m })}${alt}</div>`;
    },

    spoofHtml(m) {
      if (ABX.V0()) return "";
      if (!m.usurpation) return "";
      return `<div class="alerte-bloc">⚠ <b>Ce message se présente sous un nom connu, depuis
        une adresse qui ne l'est pas.</b>
        <div class="hint">« ${F.esc(m.from_nom)} » est enregistré au carnet, mais pas à l'adresse
          <b>${F.esc(m.from_adresse)}</b>.</div>${R.contexte("usurpation", { m })}</div>`;
    },

    lienHtml(m) {
      if (ABX.V0()) return "";
      if (!m.reference) return "";
      const src = ABX.Api.cache.message(m.reference);
      return `<div class="lien" style="margin:12px 16px">➦ <b>Message transféré par référence</b> —
        aucune copie n'a été faite : ce message pointe
        « ${F.esc(src ? src.sujet : "message supprimé")} ».
        ${src ? `<button class="hbtn" id="suivre" style="margin-top:6px">Ouvrir l'original</button>`
              : `<span class="tag">l'original n'existe plus</span>`}
        ${R.contexte("transfert.reference", { m, src })}</div>`;
    },
  };
})(window.ABX = window.ABX || {});
