/* VUE VISIONNEUSE — les pièces jointes d'un message, une par une, par-dessus le message (F154, D207).

   Ce qui s'affiche : les images (un SVG compris, mais comme IMAGE — une balise <img> n'exécute
   jamais son script), les PDF, le texte, l'audio, la vidéo. Le reste a une fiche et « Enregistrer ».

   JAMAIS DE HTML RENDU depuis une pièce jointe : elle vient d'un tiers, et la peindre dans la page
   exécuterait son code avec la session de l'utilisateur. Une pièce HTML se lit comme du TEXTE. */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt;

  function genre(mime) {
    const m = (mime || "").toLowerCase();
    if (m.startsWith("image/")) return "image";
    if (m === "application/pdf") return "pdf";
    if (m === "text/html" || m === "application/xhtml+xml") return "html";
    if (m.startsWith("text/") || m === "application/json" || m === "application/xml") return "texte";
    if (m.startsWith("audio/")) return "audio";
    if (m.startsWith("video/")) return "video";
    if (m === "message/rfc822") return "message";
    return "fichier";
  }

  function fiche(p, b, motif) {
    return `<div class="visio-fiche">
      <div class="visio-ic">${F.esc(b.ic || "📄")}</div>
      <div class="visio-fnom">${F.esc(p.nom || "pièce jointe")}</div>
      <div class="hint">${F.esc(b.mime || "type inconnu")}${b.ko ? " · " + F.esc(String(b.ko)) + " Ko" : ""}</div>
      <p class="hint">${F.esc(motif)}</p>
      <button class="hbtn prim" id="vi_enreg2">Enregistrer</button></div>`;
  }

  function corps(st) {
    const p = st.piece, b = p.b || {}, e = st.entree, g = genre(b.mime);
    if (g === "message") return `<div class="visio-fiche"><div class="visio-ic">✉</div>
      <div class="visio-fnom">${F.esc(p.nom || "message")}</div>
      <p class="hint">Cette pièce est un message.</p>
      ${p.comm_id ? `<button class="hbtn prim" id="vi_msg">Ouvrir le message</button>` : `<button class="hbtn prim" id="vi_enreg2">Enregistrer</button>`}</div>`;
    if (g === "fichier") return fiche(p, b, "Ce type de fichier ne s'affiche pas ici.");
    if (!e) return `<div class="visio-attente">Chargement…</div>`;
    if (e.erreur) return fiche(p, b, "La pièce n'a pas pu être chargée.");
    if (g === "texte" || g === "html") {
      if (e.texte == null) return fiche(p, b, "Aperçu indisponible.");
      return (g === "html" ? `<p class="hint visio-note">Page HTML montrée comme du texte : elle n'est jamais exécutée.</p>` : "")
        + `<pre class="visio-texte">${F.esc(e.texte)}</pre>`;
    }
    if (!e.url) return fiche(p, b, "Aperçu indisponible dans ce navigateur.");
    const nom = F.esc(p.nom || "");
    if (g === "image") return `<img class="visio-img" src="${F.esc(e.url)}" alt="${nom}">`;
    if (g === "pdf") return `<iframe class="visio-pdf" src="${F.esc(e.url)}" title="${nom}"></iframe>`;
    if (g === "audio") return `<audio controls src="${F.esc(e.url)}"></audio>`;
    return `<video controls class="visio-video" src="${F.esc(e.url)}"></video>`;
  }

  ABX.Views = ABX.Views || {};
  ABX.Views.Visionneuse = {
    genre,
    /* st = {piece, entree: {url, texte, erreur} | undefined, i, n} */
    render(st) {
      const p = st.piece, plusieurs = st.n > 1;
      return `<div class="visio-fond" id="vi_fond">
        <div class="visio" role="dialog" aria-modal="true" aria-label="${F.esc(p.nom || "Pièce jointe")}">
          <div class="visio-tete">
            <span class="visio-nom" title="${F.esc(p.nom || "")}">${F.esc(p.nom || "pièce jointe")}</span>
            <span class="visio-pos">${st.i + 1} / ${st.n}</span>
            <button class="hbtn" id="vi_enreg" title="Enregistrer la pièce">Enregistrer</button>
            <button class="hbtn" id="vi_fermer" title="Fermer (Échap)">✕</button>
          </div>
          <div class="visio-zone">
            ${plusieurs ? `<button class="visio-nav" id="vi_prec" title="Pièce précédente (←)">‹</button>` : ""}
            <div class="visio-corps">${corps(st)}</div>
            ${plusieurs ? `<button class="visio-nav" id="vi_suiv" title="Pièce suivante (→)">›</button>` : ""}
          </div>
        </div></div>`;
    },
  };
})(window.ABX = window.ABX || {});
