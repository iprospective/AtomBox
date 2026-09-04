/* Métriques du corpus — sert à juger la cardinalité, pas à valider. */
"use strict";
const { demarrer, creerStockage } = require("./run");
const t0 = Date.now();
const p = demarrer(creerStockage()), A = p.ABX;
const F = A.Fmt;
console.log("chargement complet  :", Date.now() - t0, "ms");
console.log("messages engendrés  :", A.Corpus.tous.length);
console.log("dossiers            :", Object.keys(A.Corpus.dossiers).length);
console.log("blobs               :", A.Attachments.blobs.length);
const pj = A.Corpus.tous.reduce((s, m) => s + m.nb_pieces_jointes, 0);
const ko = A.Corpus.tous.reduce((s, m) => s + m.pj_ko, 0);
console.log("liaisons PJ         :", pj, "(" + Math.round(100 * pj / A.Corpus.tous.length) +
  " pour 100 messages) | octets décodés :", F.poids(ko));
console.log("moyenne par message :", F.poids(Math.round(ko / A.Corpus.tous.length)),
  "décodés, soit", F.poids(Math.round(1.37 * ko / A.Corpus.tous.length)), "sur le fil",
  "— hypothèse du chapitre 08 : ~100 ko");
const part = A.Attachments.blobs.filter(b => b.refs > 1);
console.log("blobs partagés      :", part.length + "/" + A.Attachments.blobs.length,
  "→ économie", F.poids(part.reduce((s, b) => s + b.ko * (b.refs - 1), 0)));
console.log("inbox               :", A.Corpus.cnt("inbox").u, "non lus /", A.Corpus.cnt("inbox").t);
console.log("état local          :", A.Store.tailleKo(), "ko");
console.log("partielles          :", A.Registry.liste().length, "dont",
  A.Registry.liste().filter(n => n.includes("@")).length, "surcharges");
const h = p.doc.getElementById("nav").innerHTML + p.doc.getElementById("list").innerHTML;
["undefined", "NaN", "[object"].forEach(k =>
  console.log("occurrences " + JSON.stringify(k) + " :", h.split(k).length - 1));
