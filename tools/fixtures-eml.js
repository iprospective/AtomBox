#!/usr/bin/env node
/* LES MESSAGES DE LA DÉMO, en vrais fichiers .eml (RM3520 — devcamp Dolibarr, 27-29/11).

   Mathieu, 06/11 : « j'aimerais de vrais messages, de vraies pièces jointes (mais on peut faire des PDF et des images
   très simples), et bien relier les choses dans atombox avec les tags dolibarr ».

   Deux familles, toutes adressées à la boîte de démo (--mailbox) :
   1. le CORPUS DU POC — les messages que le webmail montre déjà (même graine, mêmes fichiers), pour les sociétés que le
      Dolibarr de démo connaît : mêmes correspondants, mêmes sujets, mêmes corps, mêmes fils, mêmes dates ; leurs deux
      pièces deviennent de vrais fichiers (un PDF minimal, le logo de signature — LE MÊME partout : un seul blob).
   2. les DOCUMENTS DOLIBARR — l'envoi de chaque proposition et de chaque facture (PDF joint), avec le Message-ID que
      Dolibarr leur donnerait : « …SMTPs-dolibarr-pro<id>@<hôte> ». La règle d'en-tête d'AtomBox (D187) pose alors le
      tag du document ; la réponse du client (accord, refus, règlement) le cite dans In-Reply-To/References et porte le
      même tag. Les relances d'impayés aussi. Le tag TIERS vient de la règle d'adresse (D189).

   Chaque message porte « X-AtomBox-Demo: abxpoc » : il se retrouve, et se retire.

     node tools/fixtures-eml.js --documents documents.json --mailbox test@iprospective.eu --host <hôte des Message-ID> --out DIR
     (documents.json : scripts/demo-export-documents.php du module Dolibarr) */
"use strict";
const fs = require("fs"), path = require("path"), zlib = require("zlib"), crypto = require("crypto");

const arg = (n, d) => { const i = process.argv.indexOf(n); return i > 0 ? process.argv[i + 1] : d; };
const DOCS = JSON.parse(fs.readFileSync(arg("--documents"), "utf-8"));
const BOITE = arg("--mailbox"), HOTE = arg("--host"), OUT = arg("--out");
if (!BOITE || !HOTE || !OUT) { console.error("usage : --documents F --mailbox ADRESSE --host HÔTE --out DIR"); process.exit(2); }
const MOI = { nom: DOCS.societe || "iProspective", adresse: BOITE };

// ── le POC, chargé tel quel ──────────────────────────────────────────────────────────────────────
global.window = global; global.ABX = {};
const _ls = {}; global.localStorage = { getItem: k => _ls[k] ?? null, setItem: (k, v) => { _ls[k] = String(v); }, removeItem: k => { delete _ls[k]; } };
const SRC = path.join(__dirname, "..", "webmail", "src");
for (const f of ["noyau/format.js", "noyau/store.js", "modules/pieces-jointes/service.js", "poc/prng.js", "poc/fixtures.js", "poc/corpus.js"])
  require(path.join(SRC, f));
ABX.Corpus.engendre();
const Fx = ABX.Fixtures;

// ── de vrais fichiers, très simples ─────────────────────────────────────────────────────────────
function pdf(titre, lignes) {
  // un PDF 1.4 d'une page, Helvetica, texte seul — valide (xref exacte), lisible par tout lecteur
  const esc = s => String(s).replace(/€/g, "EUR").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/[^\x20-\x7e]/g, "?").replace(/([\\()])/g, "\\$1");
  const flux = ["BT /F1 18 Tf 60 780 Td (" + esc(titre) + ") Tj ET"]
    .concat(lignes.map((l, i) => "BT /F1 11 Tf 60 " + (740 - i * 18) + " Td (" + esc(l) + ") Tj ET")).join("\n");
  const objs = ["<< /Type /Catalog /Pages 2 0 R >>", "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
    "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>",
    "<< /Length " + Buffer.byteLength(flux) + " >>\nstream\n" + flux + "\nendstream", "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"];
  let s = "%PDF-1.4\n"; const off = [];
  objs.forEach((o, i) => { off.push(Buffer.byteLength(s)); s += (i + 1) + " 0 obj\n" + o + "\nendobj\n"; });
  const x = Buffer.byteLength(s);
  s += "xref\n0 " + (objs.length + 1) + "\n0000000000 65535 f \n" + off.map(o => String(o).padStart(10, "0") + " 00000 n \n").join("")
     + "trailer\n<< /Size " + (objs.length + 1) + " /Root 1 0 R >>\nstartxref\n" + x + "\n%%EOF\n";
  return Buffer.from(s, "latin1");
}
function png(l, h, couleur) {
  // un PNG RGB : un aplat et un liseré — le « logo » de signature
  const crc = b => { let c, t = []; for (let n = 0; n < 256; n++) { c = n; for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1; t[n] = c >>> 0; }
    let r = 0xffffffff; for (const x of b) r = t[(r ^ x) & 0xff] ^ (r >>> 8); return (r ^ 0xffffffff) >>> 0; };
  const bloc = (type, data) => { const len = Buffer.alloc(4); len.writeUInt32BE(data.length); const td = Buffer.concat([Buffer.from(type), data]);
    const c = Buffer.alloc(4); c.writeUInt32BE(crc(td)); return Buffer.concat([len, td, c]); };
  const ihdr = Buffer.alloc(13); ihdr.writeUInt32BE(l, 0); ihdr.writeUInt32BE(h, 4); ihdr[8] = 8; ihdr[9] = 2;
  const brut = Buffer.alloc((l * 3 + 1) * h);
  for (let y = 0; y < h; y++) for (let x = 0; x < l; x++) {
    const bord = x < 3 || y < 3 || x >= l - 3 || y >= h - 3, o = y * (l * 3 + 1) + 1 + x * 3;
    const c = bord ? [40, 40, 60] : couleur; brut[o] = c[0]; brut[o + 1] = c[1]; brut[o + 2] = c[2];
  }
  return Buffer.concat([Buffer.from([137, 80, 78, 71, 13, 10, 26, 10]), bloc("IHDR", ihdr), bloc("IDAT", zlib.deflateSync(brut)), bloc("IEND", Buffer.alloc(0))]);
}
const LOGO = png(160, 48, [32, 110, 170]);

// ── un message RFC 5322 ─────────────────────────────────────────────────────────────────────────
const enc = s => /[^\x20-\x7e]/.test(s) ? "=?UTF-8?B?" + Buffer.from(s).toString("base64") + "?=" : s;
const adr = (nom, a) => (nom ? enc(nom) + " " : "") + "<" + a + ">";
const b64 = b => b.toString("base64").replace(/.{76}/g, "$&\r\n");
const dateRFC = t => new Date(t).toUTCString().replace("GMT", "+0000");
function eml({ de, a, sujet, corps, date, mid, irt, refs, pieces }) {
  const front = "abx-" + crypto.createHash("sha1").update(mid).digest("hex").slice(0, 16);
  const h = ["From: " + adr(de.nom, de.adresse), "To: " + adr(a.nom, a.adresse), "Subject: " + enc(sujet), "Date: " + dateRFC(date),
    "Message-ID: " + mid, ...(irt ? ["In-Reply-To: " + irt] : []), ...(refs && refs.length ? ["References: " + refs.join(" ")] : []),
    "MIME-Version: 1.0", "X-AtomBox-Demo: abxpoc", 'Content-Type: multipart/mixed; boundary="' + front + '"'];
  const parts = ["--" + front + "\r\nContent-Type: text/plain; charset=utf-8\r\nContent-Transfer-Encoding: base64\r\n\r\n" + b64(Buffer.from(corps.replace(/\n/g, "\r\n"))) + "\r\n"];
  for (const p of pieces || []) parts.push("--" + front + "\r\nContent-Type: " + p.type + '; name="' + p.nom + '"\r\nContent-Disposition: attachment; filename="' + p.nom
    + '"\r\nContent-Transfer-Encoding: base64\r\n\r\n' + b64(p.octets) + "\r\n");
  return Buffer.from(h.join("\r\n") + "\r\n\r\n" + parts.join("") + "--" + front + "--\r\n");
}

// ── 1. le corpus du POC, pour les sociétés du Dolibarr de démo ─────────────────────────────────
const parNom = new Map(DOCS.tiers.map(t => [t.nom, t]));
const sortie = []; const fils = {}; const vus = new Set();
const AXES = ["client", "fournisseur", "prospect", "partenaire"];
for (const a of AXES) for (const v of Fx.valeurs[a] || []) {
  if (!parNom.has(v.label)) continue;
  const ms = (ABX.Corpus.dossiers[v.id] || []).slice().sort((x, y) => x.date_recue - y.date_recue);
  for (const m of ms) {
    if (vus.has(m.id)) continue;           // le POC range certains messages dans deux dossiers : un seul exemplaire
    vus.add(m.id);
    const mid = "<abxpoc." + crypto.createHash("sha1").update(m.id).digest("hex").slice(0, 20) + "@demo.invalid>";
    const fil = fils[v.id + "#" + m.thread_id] = fils[v.id + "#" + m.thread_id] || [];
    const sortant = m.sens === "out", corr = sortant ? { nom: "", adresse: (m.destinataires || [])[0] } : { nom: m.from_nom, adresse: m.from_adresse };
    if (!corr.adresse || /@exemple\.fr$/.test(corr.adresse)) continue;     // une adresse interne du POC : pas d'équivalent
    const pj = (m.pieces_jointes || []).map(p => p.b && p.b.ext === "png"
      ? { nom: "signature-logo.png", type: "image/png", octets: LOGO }
      : { nom: p.nom, type: "application/pdf", octets: pdf(p.nom.replace(/\.pdf$/, ""), [v.label, m.sujet, "Document de démonstration (jeu AtomBox abxpoc)."]) });
    sortie.push({ fichier: "poc-" + sortie.length, sens: m.sens, date: m.date_recue,
      octets: eml({ de: sortant ? MOI : corr, a: sortant ? corr : MOI, sujet: m.sujet, corps: m.corps || m.snippet || "", date: m.date_recue,
                    mid, irt: fil.length ? fil[fil.length - 1] : null, refs: fil.slice(-5), pieces: pj }) });
    fil.push(mid);
  }
}
const nPoc = sortie.length;

// ── 2. les documents Dolibarr : envois, réponses, relances, règlements ─────────────────────────
const JOUR = 86400000, MAINT = Date.now();
const midDoli = (code, id, t) => "<" + Math.floor(t / 1000) + ".SMTPs-dolibarr-" + code + id + "@" + HOTE + ">";
const eur = n => n.toFixed(2).replace(".", ",") + " €";
for (const t of DOCS.tiers) {
  if (t.demo) continue;               // le tiers du scénario : ses envois sont faits pour de vrai pendant la démo
  const c = t.contacts[0] || { nom: t.nom, email: t.email }; if (!c.email) continue;
  const client = { nom: c.nom, adresse: c.email };
  for (const p of t.propositions) {
    const d0 = (p.date ? p.date * 1000 : MAINT - 20 * JOUR) - 3600000, mid = midDoli("pro", p.id, d0);
    const doc = { nom: p.ref + ".pdf", type: "application/pdf",
                  octets: pdf("Proposition commerciale " + p.ref, [MOI.nom + " - " + t.nom, "Montant HT : " + eur(p.ht), "Montant TTC : " + eur(p.ttc), "Validite : 30 jours"]) };
    sortie.push({ fichier: "doc-pro" + p.id, sens: "out", date: d0, octets: eml({ de: MOI, a: client, sujet: "Proposition " + p.ref + " — " + MOI.nom,
      corps: "Bonjour,\n\nVeuillez trouver ci-joint notre proposition " + p.ref + " d'un montant de " + eur(p.ttc) + " TTC.\n\nCordialement,\n" + MOI.nom, date: d0, mid, pieces: [doc] }) });
    if (p.etat === "signee" || p.etat === "refusee") {
      const d1 = d0 + 3 * JOUR, ok = p.etat === "signee";
      sortie.push({ fichier: "doc-pro" + p.id + "-rep", sens: "in", date: d1, octets: eml({ de: client, a: MOI, sujet: "Re: Proposition " + p.ref,
        corps: (ok ? "Bonjour,\n\nBon pour accord sur la proposition " + p.ref + ". Vous trouverez ci-joint l'exemplaire signé.\n\nBien cordialement,\n"
                   : "Bonjour,\n\nMerci pour votre proposition " + p.ref + ". Nous ne donnerons pas suite pour le moment.\n\nCordialement,\n") + c.nom
               + "\n\n> Veuillez trouver ci-joint notre proposition " + p.ref + ".",
        date: d1, mid: "<rep.pro" + p.id + "@" + t.email.split("@")[1] + ">", irt: mid, refs: [mid],
        pieces: ok ? [{ nom: p.ref + "-signee.pdf", type: "application/pdf", octets: pdf("Bon pour accord " + p.ref, [t.nom, "Signe par " + c.nom]) }] : [] }) });
    }
  }
  for (const f of t.factures) {
    const d0 = (f.date ? f.date * 1000 : MAINT - 30 * JOUR) + 3600000, mid = midDoli("inv", f.id, d0);
    const doc = { nom: f.ref + ".pdf", type: "application/pdf",
                  octets: pdf("Facture " + f.ref, [MOI.nom + " - " + t.nom, "Montant TTC : " + eur(f.ttc), "Echeance : " + new Date((f.echeance || 0) * 1000).toISOString().slice(0, 10)]) };
    sortie.push({ fichier: "doc-inv" + f.id, sens: "out", date: d0, octets: eml({ de: MOI, a: client, sujet: "Facture " + f.ref + " — " + MOI.nom,
      corps: "Bonjour,\n\nVeuillez trouver ci-joint notre facture " + f.ref + " d'un montant de " + eur(f.ttc) + " TTC.\n\nCordialement,\n" + MOI.nom, date: d0, mid, pieces: [doc] }) });
    if (f.etat === "echue") {
      const d1 = Math.min(MAINT - JOUR, (f.echeance || 0) * 1000 + 7 * JOUR);
      sortie.push({ fichier: "doc-inv" + f.id + "-relance", sens: "out", date: d1, octets: eml({ de: MOI, a: client, sujet: "Relance : facture " + f.ref + " échue",
        corps: "Bonjour,\n\nSauf erreur de notre part, la facture " + f.ref + " (" + eur(f.ttc) + " TTC) est échue. Merci de nous indiquer la date de règlement prévue.\n\nCordialement,\n" + MOI.nom,
        date: d1, mid: midDoli("inv", f.id, d1).replace(".SMTPs", ".relance.SMTPs"), irt: mid, refs: [mid], pieces: [doc] }) });
    }
    if (f.etat === "payee") {
      const d1 = d0 + 10 * JOUR;
      sortie.push({ fichier: "doc-inv" + f.id + "-reglement", sens: "in", date: Math.min(d1, MAINT - 3600000), octets: eml({ de: client, a: MOI, sujet: "Re: Facture " + f.ref,
        corps: "Bonjour,\n\nLe règlement de la facture " + f.ref + " a été effectué ce jour par virement.\n\nCordialement,\n" + c.nom,
        date: Math.min(d1, MAINT - 3600000), mid: "<reg.inv" + f.id + "@" + t.email.split("@")[1] + ">", irt: mid, refs: [mid],
        pieces: [{ nom: "avis-de-virement.png", type: "image/png", octets: png(120, 60, [60, 160, 90]) }] }) });
    }
  }
}

fs.mkdirSync(OUT, { recursive: true });
const manifeste = sortie.sort((x, y) => x.date - y.date).map((s, i) => {
  const nom = String(i).padStart(5, "0") + "-" + s.fichier + ".eml";
  fs.writeFileSync(path.join(OUT, nom), s.octets);
  return { fichier: nom, sens: s.sens, date: new Date(s.date).toISOString() };
});
fs.writeFileSync(path.join(OUT, "manifeste.json"), JSON.stringify({ boite: BOITE, marque: "abxpoc", messages: manifeste }, null, 1));
console.error(`✓ ${OUT} : ${manifeste.length} message(s) — ${nPoc} du corpus du POC, ${manifeste.length - nPoc} des documents Dolibarr`);
