/* VUE COMPOSITION — nouveau message, réponse, transfert.
   Chaque écran affiche la décision qui le rend particulier plutôt que de la
   subir en silence : l'identité d'envoi (Q026), le mode de transfert (D058/D066),
   la livraison interne hors SMTP (D012). */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, Fx = ABX.Fixtures, C = ABX.Corpus;

  ABX.Views = ABX.Views || {};
  ABX.Views.Compose = {
    render(t, ui) {
      const d = t.data, src = d.src ? ABX.Api.cache.message(d.src) : null;
      const titre = d.mode === "tr" ? "Transférer"
                  : d.mode === "new" ? "Nouveau message" : "Répondre";
      return `
        <div class="backbar"><button data-vue="liste">‹ ${F.esc(ui.folder.label)}</button></div>
        <div class="dhead"><div class="dsubj">${titre}</div>
          <div class="dmeta">${d.mode === "new" ? "message sortant"
            : "en " + (d.mode === "tr" ? "transfert" : "réponse") + " de « " +
              F.esc(src ? src.sujet : "message supprimé") + " »"}</div></div>
        <div class="compo">
          <div class="frow"><label>De</label><select id="f_de">${ABX.Ref.moi.boites.map(b =>
            `<option value="${F.esc(b.adresse)}"${d.de === b.adresse ? " selected" : ""}>${
              F.esc(b.adresse)} — ${F.esc(b.label)}</option>`).join("")}</select></div>
          ${d.mode !== "new" && d.de !== ABX.Ref.moi.boites[0].adresse
            ? `<div class="hint">↳ présélectionné sur la boîte qui a <b>reçu</b> le message —
                 répondre depuis une autre identité ampute le fil pour les collègues qui partagent
                 la boîte (Q026).</div>` : ""}
          <div class="frow"><label>À</label><input id="f_a" value="${F.esc(d.a)}"
            placeholder="destinataires, séparés par des virgules"></div>
          <div class="frow"><label>Cc</label><input id="f_cc" value="${F.esc(d.cc)}"></div>
          <div class="frow"><label>Sujet</label><input id="f_sujet" value="${F.esc(d.sujet)}"></div>
          <textarea id="f_corps">${F.esc(d.corps)}</textarea>
          ${d.mode === "tr" ? ABX.Views.Compose.sourceHtml(d, src) : ""}
          ${d.pieces_jointes.length ? `<div class="hint">📎 ${d.pieces_jointes.length} pièce(s) jointe(s) :
            ${d.pieces_jointes.map(p => F.esc(p.nom) + " (" + F.poids(p.b.ko) + ")").join(", ")}</div>` : ""}
          <div class="cbar">
            <button class="hbtn prim" id="c_env">${d.mode === "tr" ? "➦ Transférer" : "✈ Envoyer"}</button>
            <button class="hbtn" id="c_br">💾 Enregistrer le brouillon</button>
            <button class="hbtn" id="c_pj">📎 Joindre un fichier</button>
            <button class="hbtn dgr" id="c_del">✕ Abandonner</button>
          </div>
          <div class="hint">Les destinataires <b>internes</b> (@exemple.fr / .net) ne passent pas
            par le SMTP : le message est livré en base, en un seul exemplaire (D010/D012). Le piège est
            le mélange interne + externe — le relais ne doit pas re-livrer ce qui l'a déjà été.</div>
        </div>`;
    },

    /* LE BLOC SOURCE — verrouillé (D167). Le commentaire est au-dessus, dans la zone de saisie ;
       le message transmis est ici, en lecture seule, et part encapsulé tel quel (D066). On ne
       demande plus « par référence ou par copie ? » : la question porte sur un mécanisme dont la
       réponse est déjà dans la liste des destinataires, et le partage par accès est V2 (F134). */
    sourceHtml(d, src) {
      if (!src) return `<div class="lien">➦ <b>Transfert</b> — le message d'origine n'est plus
        accessible ; ce transfert partira sans lui (Q030).</div>`;
      const pj = (src.pieces_jointes || []).length;
      return `<div class="lien" id="tr_src">
        <div style="display:flex;align-items:center;gap:8px;flex-wrap:wrap">
          <span>➦ <b>Message transmis</b> — verrouillé, il part intact</span>
          <button class="hbtn" id="tr_mod" disabled title="Le modifier est une fonction de la V1 (F133)">✎ Modifier — V1</button>
        </div>
        <div class="src-fige" style="margin-top:6px">
          <div class="dmeta">${F.esc(src.from_nom || src.from_adresse || "")} —
            ${F.esc(src.sujet || "(sans sujet)")}${pj ? " · 📎 " + pj : ""}</div>
          <pre class="src-corps">${F.esc((src.corps || src.snippet || "").slice(0, 4000))}</pre>
        </div>
        <div class="hint" style="margin-top:5px">Ce que vous écrivez au-dessus est <b>votre</b>
          commentaire : il ne se mélange pas au message d'origine, et l'index ne retrouvera pas ce
          fil dix fois pour un mot cité neuf fois (D163). L'original part <b>encapsulé</b> en
          <code>message/rfc822</code> (D066) — une copie sort, elle ne se reprend pas.</div></div>`;
    },
  };
})(window.ABX = window.ABX || {});
