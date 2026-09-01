/* VUE MESSAGE — l'onglet ouvert sur un message.
   La barre d'actions change selon l'état du message : un message à la corbeille
   ne s'archive pas, un message sorti de la file se remet en file (Q09). */
(function (ABX) {
  "use strict";
  const R = ABX.Registry, F = ABX.Fmt, Fx = ABX.Fixtures, C = ABX.Corpus;

  ABX.Views = ABX.Views || {};
  ABX.Views.Message = {
    render(m, ui) {
      const fil = C.tous.filter(x => x.thread === m.thread && x.fid === m.fid)
                        .sort((a, b) => a.date - b.date).slice(0, 4);
      const dossiers = Fx.UTIL.map(u =>
        `<option value="${F.esc(u.id)}"${m.dossier === u.id ? " selected" : ""}>${F.esc(u.label)}</option>`).join("");

      return `
        <div class="backbar"><button data-vue="liste">‹ ${F.esc(ui.folder.label)}</button></div>
        <div class="dhead">
          <div class="dsubj">${F.esc(m.subject)}</div>
          <div class="dmeta">${F.esc(m.from)} &lt;${F.esc(m.mail)}&gt; ·
            ${new Date(m.date).toLocaleString("fr-FR")} · reçu sur <b>${F.esc(m.boite)}</b>
            ${m.pj ? " · 📎 " + m.pj : ""}
            ${m.motif ? " · " + R.render("statut.chip", { m }) : ""}
            ${m.dossier === "trash" ? ` · <span class="tag">corbeille</span>` : ""}</div>
          <div class="dacts">
            <button class="hbtn" data-c="rep">↩ Répondre</button>
            <button class="hbtn" data-c="reptous">↩↩ Répondre à tous</button>
            <button class="hbtn" data-c="tr">➦ Transférer</button>
            <button class="hbtn" data-a="tag">🏷 Taguer</button>
            ${m.dossier === "trash"
              ? `<button class="hbtn" data-x="restaurer">↩ Restaurer</button>
                 <button class="hbtn dgr" data-x="supprimer">✕ Supprimer définitivement</button>`
              : `${m.motif
                   ? `<button class="hbtn" data-x="refile">↺ Remettre dans la file</button>`
                   : `<button class="hbtn" data-x="traiter">✓ Traité</button>
                      <button class="hbtn" data-x="archiver">🗄 Archiver</button>`}
                 <button class="hbtn" data-x="${m.lu ? "nonLu" : "lire"}">${m.lu ? "◻ Non lu" : "◼ Lu"}</button>
                 <button class="hbtn" data-x="junk">🚫 Indésirable</button>
                 <button class="hbtn" data-x="corbeille">🗑 Corbeille</button>`}
            <button class="hbtn" data-a="orig">⤓ .eml</button>
            <select class="sortsel" id="dep" style="margin-left:0">
              <option value="">Déplacer vers…</option>${dossiers}</select>
          </div>
        </div>
        ${ABX.Views.Message.lienHtml(m)}
        <div class="box"><h4>Tags — plusieurs applications, sans écrasement (D17/D20)</h4>
          ${m.tags.length ? m.tags.map(x => `<div class="kv"><span class="k">${F.esc(x.axe)}</span>
            <span class="v"><b>${F.esc(x.val)}</b>
            <span class="tag">posé par ${F.esc(x.src)}</span></span></div>`).join("")
            : `<div class="dmeta">aucun tag</div>`}
        </div>
        ${R.render("erp.panel", { m })}
        ${R.render("attachment.list", { m })}
        <div class="box"><h4>Fil de discussion (${fil.length} messages)</h4>
          <div class="dmeta">thread_id matérialisé — D55</div></div>
        <div class="thread">${fil.map(x =>
          R.render("thread.item", { x, courant: x.id === m.id })).join("")}</div>`;
    },

    /* Un transfert par référence n'est pas une copie : c'est un pointeur, et un
       pointeur peut mourir (Q30). L'écran doit le dire, pas le cacher. */
    lienHtml(m) {
      if (!m.ref) return "";
      const src = C.par(m.ref);
      return `<div class="lien" style="margin:12px 16px">➦ <b>Message transféré par référence</b> —
        aucune copie n'a été faite : ce message pointe
        « ${F.esc(src ? src.subject : "message supprimé")} » (D58/D67).
        ${src ? `<button class="hbtn" id="suivre" style="margin-top:6px">Ouvrir l'original</button>`
              : `<span class="tag">l'original n'existe plus — le lien est mort (Q30)</span>`}</div>`;
    },
  };
})(window.ABX = window.ABX || {});
