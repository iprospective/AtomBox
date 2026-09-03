/* RENDU MARKDOWN MINIMAL — juste ce que le CDC utilise : titres, paragraphes,
   listes, citations, tableaux, code, gras, italique, barré, liens, filets.
   Pas de bibliothèque : le POC n'a aucune dépendance, et le CDC n'a besoin
   de rien d'autre. Le HTML source est échappé AVANT toute transformation.

   Les liens internes du CDC (cdc-rm2881-NN-….md, avec ou sans ancre)
   deviennent des liens de navigation dans la page « CDC » : data-chap="NN". */
(function (ABX) {
  "use strict";
  const esc = s => String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;")
                            .replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  function inline(t) {
    t = esc(t);
    t = t.replace(/`([^`]+)`/g, (_, c) => "<code>" + c + "</code>");
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, (_, lib, url) => {
      const m = url.match(/cdc-rm2881-(\d+)-[^)#]*\.md(#.*)?$/);
      if (m) return `<a href="#" class="cdc-lien" data-chap="${m[1]}">${lib}</a>`;
      return `<a href="${url}" target="_blank" rel="noopener">${lib}</a>`;
    });
    t = t.replace(/\*\*([^*]+)\*\*/g, "<b>$1</b>");
    t = t.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<i>$2</i>");
    t = t.replace(/~~([^~]+)~~/g, "<s>$1</s>");
    /* D138, Q54, C09 : cliquables vers leur section quand elle existe */
    t = t.replace(/\b([DQC]\d{2,3}b?)\b/g, (m0, id) =>
      ABX.CDC && ABX.CDC.sections && ABX.CDC.sections[id]
        ? `<a href="#" class="cdc-lien" data-sec="${id}">${id}</a>` : m0);
    return t;
  }

  function table(lignes) {
    const cel = l => l.replace(/^\||\|$/g, "").split("|").map(c => c.trim());
    const tete = cel(lignes[0]), corps = lignes.slice(2).map(cel);
    return `<table class="erpl"><tr>${tete.map(c => "<th>" + inline(c) + "</th>").join("")}</tr>` +
      corps.map(r => "<tr>" + r.map(c => "<td>" + inline(c) + "</td>").join("") + "</tr>").join("") +
      "</table>";
  }

  function rendre(md) {
    const L = String(md || "").split("\n"), out = [];
    let i = 0;
    const paraFin = () => {};
    while (i < L.length) {
      const l = L[i];
      if (/^```/.test(l)) {                         // bloc de code
        const buf = []; i++;
        while (i < L.length && !/^```/.test(L[i])) buf.push(L[i++]);
        i++; out.push("<pre class=\"md-code\">" + esc(buf.join("\n")) + "</pre>"); continue;
      }
      if (/^\s*$/.test(l)) { i++; continue; }
      if (/^---+\s*$/.test(l)) { out.push("<hr>"); i++; continue; }
      const h = l.match(/^(#{1,6})\s+(.*)$/);
      if (h) { const n = Math.min(h[1].length + 1, 6);
        out.push(`<h${n}>${inline(h[2])}</h${n}>`); i++; continue; }
      if (/^\|/.test(l)) {                          // tableau
        const buf = []; while (i < L.length && /^\|/.test(L[i])) buf.push(L[i++]);
        out.push(buf.length >= 2 ? table(buf) : "<p>" + inline(buf.join(" ")) + "</p>"); continue;
      }
      if (/^>/.test(l)) {                           // citation (multi-lignes)
        const buf = []; while (i < L.length && /^>/.test(L[i])) buf.push(L[i++].replace(/^>\s?/, ""));
        out.push("<blockquote>" + rendre(buf.join("\n")) + "</blockquote>"); continue;
      }
      const li = l.match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
      if (li) {                                     // liste (un niveau, items multi-lignes)
        const ord = /\d/.test(li[2]), items = [];
        while (i < L.length) {
          const m = L[i].match(/^(\s*)([-*]|\d+\.)\s+(.*)$/);
          if (m) { items.push(m[3]); i++; }
          else if (/^\s{2,}\S/.test(L[i]) && items.length) { items[items.length - 1] += " " + L[i].trim(); i++; }
          else break;
        }
        out.push(`<${ord ? "ol" : "ul"}>` + items.map(x => "<li>" + inline(x) + "</li>").join("") + `</${ord ? "ol" : "ul"}>`);
        continue;
      }
      const buf = [];                                // paragraphe
      while (i < L.length && !/^\s*$/.test(L[i]) && !/^(#|\||>|```|---|\s*[-*]\s|\s*\d+\.\s)/.test(L[i])) buf.push(L[i++]);
      if (!buf.length) { buf.push(L[i++]); }
      out.push("<p>" + inline(buf.join(" ")) + "</p>");
    }
    return out.join("\n");
  }

  ABX.Markdown = { rendre, inline };
})(window.ABX = window.ABX || {});
