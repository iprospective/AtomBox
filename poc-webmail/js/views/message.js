/* VUE MESSAGE — l'onglet ouvert sur un message.
   La barre d'actions change selon l'état du message : un message à la corbeille
   ne s'archive pas, un message sorti de la file se remet en file (Q009). */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt, Fx = ABX.Fixtures, C = ABX.Corpus;

  ABX.Views = ABX.Views || {};
  ABX.Views.Message = {
    render(m, ui) {
      const fil = C.tous.filter(x => x.thread === m.thread && x.fid === m.fid)
                        .sort((a, b) => a.date - b.date).slice(0, 4);
      return `
        <div class="backbar"><button data-vue="liste">‹ ${F.esc(ui.folder.label)}</button></div>
        <div class="dhead">
          <div class="dsubj">${F.esc(m.subject)}</div>
          <div class="dmeta">${R.render("expediteur", { m, long: true })} ·
            ${new Date(m.date).toLocaleString("fr-FR")} · reçu sur <b>${F.esc(m.boite)}</b>
            ${m.pj ? " · 📎 " + m.pj : ""}
            ${m.motif ? " · " + R.render("statut.chip", { m }) : ""}
            ${m.dossier === "trash" ? ` · <span class="tag">corbeille</span>` : ""}</div>
          <div class="dacts">
            <button class="hbtn${m.repond === "non" ? " off" : ""}" data-c="rep"
              ${m.repond === "non" ? `disabled title="Cette adresse a rejeté une réponse` +
                ` — voir le bandeau ci-dessous (D131)"` : ""}>↩ Répondre</button>
            <button class="hbtn${m.repond === "non" ? " off" : ""}" data-c="reptous"
              ${m.repond === "non" ? "disabled" : ""}>↩↩ Tous</button>
            <button class="hbtn" data-c="tr">➦ Transférer</button>
            ${ABX.Views.Message.statutHtml(m)}
            <button class="hbtn ic" data-x="${m.lu ? "nonLu" : "lire"}"
              title="${m.lu ? "Marquer non lu" : "Marquer lu"}">${m.lu ? "◻" : "◼"}</button>
            <span class="pousse"></span>
            <button class="hbtn ic" id="plus" title="Autres actions">⋯</button>
            ${(m.dossier || m.fid) === "trash"
              ? `<button class="hbtn ic" data-x="restaurer" title="Restaurer">↩</button>
                 <button class="hbtn ic dgr" data-x="supprimer" title="Supprimer définitivement">✕</button>`
              : `<button class="hbtn ic" data-x="${(m.dossier || m.fid) === "junk" ? "nonJunk" : "junk"}"
                   title="${(m.dossier || m.fid) === "junk"
                     ? "Ce n'est pas un indésirable" : "Marquer indésirable"}">${
                     (m.dossier || m.fid) === "junk" ? "✓" : "🚫"}</button>
                 <button class="hbtn ic dgr" data-x="corbeille"
                   title="Mettre à la corbeille">🗑</button>`}
          </div>
          ${ABX.Views.Message.menuHtml(m)}
        </div>
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
      if (m.motif === "archive") return `<span class="tag">archivé</span>
        <button class="hbtn" data-x="refile" title="Remettre dans la file">↺ Reprendre</button>`;
      return `<select class="statsel st-${F.esc(m.statut || "nouveau")}" id="stat"
          title="Statut de traitement">
        ${Fx.STATUTS.map(x => `<option value="${x.id}"${x.id === m.statut ? " selected" : ""}
          >${x.ic} ${F.esc(x.label)}</option>`).join("")}</select>`;
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
        ${Fx.UTIL.map(u => `<button data-move="${F.esc(u.id)}">${u.icon} ${F.esc(u.label)}</button>`).join("")}
        <button data-move="">↩ Retirer du dossier</button>
        <div class="mgrp">Suite collaborative</div>
        <button data-m="tache">${cap("taches").ic} Créer une tâche
          <span class="mprov">${F.esc(cap("taches").label)}</span></button>
        <button data-m="contact">${cap("contacts").ic} Fiche du correspondant
          <span class="mprov">${F.esc(cap("contacts").label)}</span></button>
        ${m.pj ? `<button data-m="fichiers">${cap("fichiers").ic} Enregistrer les pièces jointes
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
    fiabiliteHtml(m) {
      if (ABX.V0()) return "";
      if (m.sens === "out" || m.fiab === undefined || m.spoof) return "";
      if (m.fiab >= 2)
        return `<div class="lien fiab-bloc" style="margin:12px 16px">✓ <b>Expéditeur
          validé</b> — quelqu'un de chez vous a marqué cette adresse comme fiable, et ce
          message est authentifié par son domaine (DMARC aligné).
          <div class="hint">La validation ne fait pas taire les règles fortes du catalogue
            (D128) : elle atténue les indices faibles, elle n'ouvre pas de porte. Et elle
            s'éteint d'elle-même si le domaine cesse d'être authentifiable ou si les
            habitudes de l'expéditeur changent (D137, B3).</div></div>`;
      if (!m.dom.aligne)
        return `<div class="lien" style="margin:12px 16px">◌ <b>Ce message n'est pas
          authentifié par son domaine.</b>
          <div class="hint">Aucun indicateur de confiance ne peut donc s'afficher, même si
            l'adresse est connue : rien ne prouve que ce message-ci vienne d'elle (D137).
            ${m.connu ? "L'expéditeur est pourtant à votre carnet — c'est exactement le cas où un affichage rassurant serait une faute." : ""}</div>
          <button class="hbtn" style="margin-top:6px" disabled
            title="Impossible : on ne valide pas une adresse sur un message non authentifié">
            Marquer cet expéditeur comme fiable</button></div>`;
      return `<div class="lien" style="margin:12px 16px">· Expéditeur connu, message
        authentifié — <b>aucune validation humaine</b>.
        <div class="hint">Vous pouvez marquer cette adresse comme fiable. La portée par
          défaut est <b>cette boîte</b> ; un gestionnaire de domaine peut valider pour tout
          le monde (D106, D137).</div>
        <button class="hbtn" style="margin-top:6px">Marquer cet expéditeur comme fiable</button>
        </div>`;
    },

    repondHtml(m) {
      if (ABX.V0()) return "";
      if (!m.repond || m.repond === "oui") return "";
      const alt = m.alt
        ? `<br>Plutôt que d'abandonner : <b>${F.esc(m.alt.nom)}</b>
           &lt;${F.esc(m.alt.mail)}&gt; est à votre carnet, sur le même domaine —
           montré, jamais présélectionné : une réponse destinée à un automate
           n'était pas destinée à un humain.`
        : "";
      if (m.repond === "non")
        return `<div class="alerte-bloc">⛔ <b>Cette adresse n'accepte pas les réponses —
          et ce n'est pas une supposition.</b>
          <div class="hint">Une réponse envoyée il y a ${m.dsn.jours} jours à
            <b>${F.esc(m.mail)}</b> a été rejetée : <code>${F.esc(m.dsn.code)}</code>.
            AtomBox le sait parce qu'il a <b>essayé</b>, et parce qu'il a gardé le retour
            (D119, D131) — là où les autres messageries devinent à partir du mot
            « noreply ». La marque porte une date et se réévalue : un 5xx n'est pas
            éternel.${alt}</div></div>`;
      return `<div class="lien" style="margin:12px 16px">✉ <b>${
        m.nature === "liste" ? "Message de diffusion" : "Notification automatique"}</b> —
        l'expéditeur déclare ne pas lire les réponses. Répondre reste possible en un clic ;
        ce n'est simplement plus l'action principale (D131).
        <div class="hint">${m.nature === "liste"
          ? `L'action utile ici n'est pas « répondre », c'est <b>se désabonner</b> —
             en-tête <code>List-Unsubscribe</code>, D132. Jamais automatiquement : un lien
             de désabonnement suivi sans geste humain est un confirmateur d'adresse.`
          : `Une notification <b>entre</b> dans la file des non traités : c'est une machine
             qui attend quelque chose de vous (D130).`}${alt}</div></div>`;
    },

    /* D126/D128 — le bandeau ne crie que sur un signal FORT (une règle ★ de B),
       jamais sur « expéditeur inconnu » seul : la moitié du courrier d'une PME
       vient d'un inconnu, et une alerte qui se déclenche une fois sur deux n'est
       plus lue au bout d'une semaine. Le silence est une fonctionnalité. */
    spoofHtml(m) {
      if (ABX.V0()) return "";
      if (!m.spoof) return "";
      const sosie = /iprospect/.test(m.mail.split("@")[1] || "");
      return `<div class="alerte-bloc">⚠ <b>Ce message se présente sous un nom connu,
        depuis une adresse qui ne l'est pas.</b>
        <div class="hint">« ${F.esc(m.from)} » est enregistré au carnet, mais pas à
          l'adresse <b>${F.esc(m.mail)}</b>. Règle <b>B1</b> du catalogue (D128) —
          le meilleur signal du lot, et celui qu'aucun anti-spam générique ne peut
          produire : il demande de connaître <i>vos</i> correspondants.
          ${sosie ? `<br>S'y ajoute la règle <b>A8</b> : le domaine est un
            <b>sosie</b> d'un domaine que vous connaissez.` : ""}
          <br>AtomBox <b>alerte</b>, il ne rejette pas — l'analyse d'usurpation est
          probabiliste, et un rejet silencieux coûte plus cher qu'une bannière de
          trop (Q049).</div></div>`;
    },

    /* Un transfert par référence n'est pas une copie : c'est un pointeur, et un
       pointeur peut mourir (Q030). L'écran doit le dire, pas le cacher. */
    lienHtml(m) {
      if (ABX.V0()) return "";          // V0 : le transfert est par copie, pas par référence
      if (!m.ref) return "";
      const src = C.par(m.ref);
      return `<div class="lien" style="margin:12px 16px">➦ <b>Message transféré par référence</b> —
        aucune copie n'a été faite : ce message pointe
        « ${F.esc(src ? src.subject : "message supprimé")} » (D058/D067).
        ${src ? `<button class="hbtn" id="suivre" style="margin-top:6px">Ouvrir l'original</button>`
              : `<span class="tag">l'original n'existe plus — le lien est mort (Q030)</span>`}</div>`;
    },
  };
})(window.ABX = window.ABX || {});
