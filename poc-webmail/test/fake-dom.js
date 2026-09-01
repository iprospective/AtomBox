/* DOM minimal pour exécuter le POC hors navigateur.
   Ne parse que ce dont les contrôleurs ont besoin : les balises ouvrantes et
   leurs attributs. Suffisant pour vérifier que le câblage tient. */
"use strict";

function attrs(s) {
  const a = {};
  s.replace(/([\w:-]+)(?:="([^"]*)")?/g, (_, k, v) => { a[k] = v == null ? "" : v; return ""; });
  return a;
}

function mkEl(tag, a, html) {
  const cls = (a.class || "").split(/\s+/).filter(Boolean);
  const el = {
    tagName: tag.toUpperCase(), id: a.id || "", _attrs: a, _cls: cls,
    innerHTML: html || "", value: a.value || "", textContent: "", scrollTop: 0,
    dataset: Object.keys(a).reduce((o, k) => {
      if (k.startsWith("data-")) o[k.slice(5).replace(/-(\w)/g, (_, c) => c.toUpperCase())] = a[k];
      return o; }, {}),
    classList: {
      add: c => cls.includes(c) || cls.push(c),
      remove: c => { const i = cls.indexOf(c); if (i >= 0) cls.splice(i, 1); },
      toggle: (c, on) => on === undefined ? (cls.includes(c) ? el.classList.remove(c) : cls.push(c))
                                          : (on ? el.classList.add(c) : el.classList.remove(c)),
      contains: c => cls.includes(c),
    },
    focus() {}, setSelectionRange() {}, closest: () => null,
    selectedOptions: [{ text: a.value || "opt" }],
    querySelectorAll: sel => enfants(el).filter(x => matche(x, sel)),
    querySelector: sel => enfants(el).find(x => matche(x, sel)) || null,
  };
  return el;
}

function enfants(el) {
  if (el._enfants && el._html === el.innerHTML) return el._enfants;
  const out = [];
  const re = /<(\w+)([^>]*?)\/?>/g;
  let m;
  while ((m = re.exec(el.innerHTML))) out.push(mkEl(m[1], attrs(m[2])));
  el._html = el.innerHTML; el._enfants = out;
  return out;
}

/* Sélecteurs pris en charge : #id, .cls, [attr], tag, et leurs combinaisons
   simples ; « A B » est traité comme B (le POC n'en a pas besoin de plus). */
function matche(el, sel) {
  const dernier = sel.trim().split(/\s+/).pop();
  const parts = dernier.match(/(^\w+)|(#[\w-]+)|(\.[\w-]+)|(\[[\w-]+(?:=[^\]]+)?\])/g) || [];
  return parts.every(p => {
    if (p[0] === "#") return el.id === p.slice(1);
    if (p[0] === ".") return el._cls.includes(p.slice(1));
    if (p[0] === "[") { const k = p.slice(1, -1).split("=")[0]; return k in el._attrs; }
    return el.tagName === p.toUpperCase();
  });
}

function creerDocument() {
  const racine = {};
  /* Les éléments écrits en dur dans index.html (barre du POC) : le harnais ne
     parse pas le HTML, il les fabrique à la demande pour que le câblage tienne. */
  const STATIQUES = {
    ".pocnav [data-page]": ["aide", "features", "cdc", "roadmap"]
      .map(p => mkEl("button", { "data-page": p })),
  };
  const doc = {
    _els: racine, _statiques: STATIQUES,
    getElementById(id) { return racine[id] = racine[id] || mkEl("div", { id }); },
    querySelectorAll(sel) { return STATIQUES[sel] || []; },
    querySelector(sel) { return (STATIQUES[sel] || [])[0] || null; },
    documentElement: { _t: null, getAttribute() { return this._t; }, setAttribute(k, v) { this._t = v; } },
  };
  return doc;
}

function creerStockage(initial) {
  const data = { ...(initial || {}) };
  return { data,
    getItem: k => (k in data ? data[k] : null),
    setItem: (k, v) => { data[k] = String(v); },
    removeItem: k => { delete data[k]; } };
}

/* Fabrique un événement de clic dont `closest` répond comme dans un navigateur. */
function evt(cible) {
  return { target: { closest: sel => {
      const k = sel.replace(/[[\]]/g, "");
      return cible && k in cible._attrs ? cible : null; } },
    stopPropagation() {}, preventDefault() {}, button: 0 };
}

module.exports = { creerDocument, creerStockage, mkEl, matche, evt };
