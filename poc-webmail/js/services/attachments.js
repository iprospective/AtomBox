/* MAGASIN D'OCTETS DÉDUPLIQUÉ (D011 / D024 / D032).

   Le BLOB porte les octets, le sha256 et le type DÉTECTÉ.
   La LIAISON porte le nom de fichier, le type DÉCLARÉ et l'encodage d'origine.
   Deux messages peuvent nommer le même octet différemment, et un client mail
   déclare parfois n'importe quoi : les deux faits doivent survivre au stockage. */
(function (ABX) {
  "use strict";
  /* Le PRNG n'existe qu'en POC (D141) : en prod ce service ne fabrique rien, il
     ne fait qu'indexer ce que l'API sert. Les tirages sont donc optionnels. */
  const P = ABX.PRNG || { int: () => 0, pick: a => a[0], next: () => 0, hex: n => "0".repeat(n) };
  const { int, pick, next, hex } = { int: (...a) => P.int(...a), pick: a => P.pick(a),
                                     next: () => P.next(), hex: n => P.hex(n) };

  const XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet";
  const DOCX = "application/vnd.openxmlformats-officedocument.wordprocessingml.document";

  const blobs = [];
  const blob = o => { const b = { pj_id: blobs.length + 1, sha: hex(12), refs: 1, ...o };
                      blobs.push(b); return b; };

  /* Les blobs RÉCURRENTS : à eux seuls, ils justifient la déduplication.
     Le reste des fichiers est unique — et c'est le cas le plus fréquent. */
  const RECURRENTS = [
    blob({ p:72, nom:"signature-logo", ext:"png",  mime:"image/png",       ko:34,   ic:"🖼", refs:1284 }),
    blob({ p:15, nom:"CGV-2026",       ext:"pdf",  mime:"application/pdf", ko:212,  ic:"📄", refs:96 }),
    blob({ p:9,  nom:"tarifs-2026",    ext:"xlsx", mime:XLSX,              ko:344,  ic:"📊", refs:41 }),
    blob({ p:4,  nom:"plaquette-2026", ext:"pdf",  mime:"application/pdf", ko:2460, ic:"📄", refs:18, photo:true }),
  ];

/* La distribution compte autant que les types : dans une boîte réelle, une pièce
     jointe sur deux est un PDF de quelques centaines de kilo-octets, et la photo de
     plusieurs méga est rare — mais c'est elle qui fait le volume. Le champ `p` est ce
     poids de tirage.

     Ces bornes sont CALÉES pour que le corpus tombe autour de 100 ko par message
     sur le fil, l'hypothèse du chapitre 08 (100 boîtes × 50 000 emails × 100 ko).
     Sans ce calage, un tirage uniforme donne plus d'un méga par message et la
     maquette raconterait un volume qu'elle n'a pas mesuré. La vraie distribution
     ne se saura qu'en ingérant le pilote — c'est même l'une des premières choses
     que ce pilote devra produire. Voir test/metrics.js. */
  const TYPES = [
    { p:34, ext:"pdf",  mime:"application/pdf", ic:"📄", ko:[30,300],
      noms:["Facture {n}","Devis {n}","BL {n}","Contrat de maintenance","Releve {n}"] },
    { p:26, ext:"pdf",  mime:"application/pdf", ic:"📄", ko:[30,240],
      noms:["Avoir {n}","Bon de commande {n}","Attestation {n}"] },
    { p:3,  ext:"jpg",  mime:"image/jpeg", ic:"🖼", ko:[900,2600], photo:true,
      noms:["IMG_{n}","photo-chantier-{n}","montage-{n}"] },
    { p:9,  ext:"png",  mime:"image/png",  ic:"🖼", ko:[60,700], photo:true,
      noms:["capture-{n}","schema-{n}"] },
    { p:11, ext:"xlsx", mime:XLSX, ic:"📊", ko:[18,320],  noms:["inventaire-{n}","suivi-commandes-{n}"] },
    { p:10, ext:"docx", mime:DOCX, ic:"📝", ko:[24,260],  noms:["compte-rendu-{n}","cahier-des-charges-{n}"] },
    { p:2,  ext:"zip",  mime:"application/zip", ic:"🗜", ko:[400,2400], noms:["dossier-{n}","photos-chantier-{n}"] },
    { p:4,  ext:"eml",  mime:"message/rfc822",  ic:"✉", ko:[14,180], eml:true, noms:["message-transfere-{n}"] },
  ];
  function tirerPondere(liste) {
    let r = next() * liste.reduce((s, t) => s + t.p, 0);
    for (const t of liste) { r -= t.p; if (r <= 0) return t; }
    return liste[0];
  }
  const tirerType = () => tirerPondere(TYPES);

  /* La liaison. Le type déclaré diverge parfois du type détecté : c'est le cas réel. */
  function lien(b, noms) {
    const base = noms ? pick(noms).replace("{n}", "" + int(1000, 9999)) : b.nom;
    return { b, nom: base + "." + b.ext,
             declare: next() < .12 ? "application/octet-stream" : b.mime,
             enc: b.ext === "eml" ? "8bit" : "base64" };
  }

  const Attachments = {
    blobs, RECURRENTS, TYPES, blob, lien,

    /* Attache des pièces jointes à un message et en déduit son poids réel. */
    attacher(m) {
      m.pjs = [];
      /* Une pièce jointe le plus souvent, deux ou trois parfois. */
      if (next() < .22) { const n = next() < .78 ? 1 : int(2, 3);
        for (let k = 0; k < n; k++) { const t = tirerType();
          m.pjs.push(lien(blob({ ext:t.ext, mime:t.mime, ic:t.ic, photo:t.photo, eml:t.eml,
            ko: int(t.ko[0], t.ko[1]), refs: next() < .15 ? int(2, 6) : 1 }), t.noms)); } }
      if (next() < .14) m.pjs.push(lien(tirerPondere(RECURRENTS)));  // signature, CGV, tarifs…
      Attachments.recompter(m);
    },

    /* +37 % sur le fil : c'est le coût du base64 (D069), et l'écart qui explique
       l'audit de dimensionnement du chapitre 08. */
    recompter(m) {
      m.pj = m.pjs.length;
      m.pj_ko = m.pjs.reduce((s, p) => s + p.b.ko, 0);
      m.size = int(3, 26) + Math.round(m.pj_ko * 1.37);   // le corps seul pèse peu
    },

    /* Pièce jointe ajoutée à la composition. */
    simulee() {
      const t = tirerType();
      return lien(blob({ ext:t.ext, mime:t.mime, ic:t.ic, photo:t.photo, eml:t.eml,
                         ko: int(t.ko[0], t.ko[1]), refs:1 }), t.noms);
    },

    /* Encapsulation d'un message dans un autre — dédupliquée comme un message (D066). */
    encapsuler(src) {
      return lien(blob({ ext:"eml", mime:"message/rfc822", ic:"✉",
        ko: Math.max(8, Math.round(src.size)), eml:true, refs:1 }), null);
    },

    recompressable: b => !!b.photo && b.ko > 2000,
    gain: b => Math.round(b.ko * .62),
  };

  ABX.Attachments = Attachments;
})(window.ABX = window.ABX || {});
