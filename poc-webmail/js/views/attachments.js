/* GESTION DES PIÈCES JOINTES — chercher, renommer, taguer, enregistrer.

   L'écran repose sur une distinction que rien d'autre ne rend visible : le NOM
   appartient à la liaison, les OCTETS au blob (D32). Renommer une pièce jointe,
   c'est donc renommer *sa liaison* — les autres messages qui portent le même
   octet gardent leur nom, et le message d'origine n'est pas altéré (D25). */
(function (ABX) {
  "use strict";
  const F = ABX.Fmt, C = ABX.Corpus, At = ABX.Attachments;

  /* Toutes les liaisons du corpus, à plat — c'est la vue « fichiers ». */
  function toutes() {
    const out = [];
    C.tous.forEach(m => (m.pjs || []).forEach((p, i) =>
      out.push({ m, p, i, b: p.b })));
    return out;
  }

  function filtrer(q, type) {
    const f = (q || "").trim().toLowerCase();
    return toutes().filter(x =>
      (!f || x.p.nom.toLowerCase().includes(f) || x.m.subject.toLowerCase().includes(f)) &&
      (!type || type === "tous" || x.b.ext === type))
      .sort((a, b) => b.m.date - a.m.date).slice(0, 60);
  }

  ABX.Views = ABX.Views || {};
  ABX.Views.Attachments = {
    toutes, filtrer,
    render(ui) {
      const q = ui.pjq || "", type = ui.pjtype || "tous";
      const liste = filtrer(q, type);
      const tot = toutes();
      const octets = tot.reduce((s, x) => s + x.b.ko, 0);
      const uniques = new Set(tot.map(x => x.b.pj_id)).size;
      const gain = octets - [...new Map(tot.map(x => [x.b.pj_id, x.b])).values()]
        .reduce((s, b) => s + b.ko, 0);
      const TYPES = ["tous","pdf","jpg","png","xlsx","docx","zip","eml"];

      return `<div class="backbar"><button data-vue="liste">‹ Retour</button></div>
        <div class="dhead"><div class="dsubj">Pièces jointes</div>
          <div class="dmeta">${tot.length} liaison(s) pour ${uniques} blob(s) —
            ${F.poids(octets)} nommés, <b>${F.poids(octets - gain)} réellement stockés</b>
            (${gain > 0 ? F.poids(gain) + " économisés par la déduplication" : "aucun partage"})</div>
          <div class="frow" style="margin-top:9px">
            <input id="pjq" value="${F.esc(q)}" placeholder="Chercher un nom de fichier ou un sujet…">
          </div>
          <div class="chips">${TYPES.map(t =>
            `<span class="chip${t === type ? " on" : ""}" data-pjt="${t}">${t}</span>`).join("")}</div>
        </div>
        <div class="admin">
          ${liste.length ? liste.map((x, k) => `<div class="pjrow" data-k="${k}">
            <span class="pic">${x.b.ic}</span>
            <div class="pjn">
              <input class="pjname" data-k="${k}" value="${F.esc(x.p.nom)}">
              <div class="ps">${F.poids(x.b.ko)} · ${F.esc(F.mimeC(x.b.mime))} ·
                <span class="hash">sha256:${x.b.sha}…</span>
                ${x.b.refs > 1 ? `<span class="badge ok">${x.b.refs} liaisons</span>` : ""}
                ${At.recompressable(x.b)
                  ? `<span class="badge w">recompressible · ${F.poids(At.gain(x.b))}</span>` : ""}
              </div>
              <div class="ps">↳ ${F.esc(x.m.subject)} — ${F.esc(x.m.from)} · ${F.dt(x.m.date)}</div>
            </div>
            <div class="pjacts">
              <button class="hbtn ic" data-pja="ouvrir" data-k="${k}" title="Ouvrir le message">✉</button>
              <button class="hbtn ic" data-pja="taguer" data-k="${k}" title="Taguer">🏷</button>
              <button class="hbtn ic" data-pja="deposer" data-k="${k}"
                title="Enregistrer — ${F.esc(ABX.Providers.actif("fichiers").label)}">💾</button>
            </div>
          </div>`).join("")
          : `<div class="empty">Aucune pièce jointe ne correspond.</div>`}
          <div class="hint" style="margin:12px">Renommer ici modifie la <b>liaison</b>, pas le
            blob : les autres messages qui portent les mêmes octets gardent leur nom, et le
            message d'origine reste reconstructible à l'identique (D25/D32). C'est la seule
            forme de renommage qui ne casse pas la signature.</div>
        </div>`;
    },
  };
})(window.ABX = window.ABX || {});
