/* Blok "proyek lain dari Nopal Brainwork": satu sumber (ekosistem.json) untuk link bio Nopal, NolKaryawan, dan Skalarium.
   Pasang di halaman: <section class="eko" data-ekosistem="<id situs>">(markup cadangan dari ekosistem/blok.py)</section>
   lalu <script src="https://brainwork-cloud.github.io/brainwork-konten/ekosistem/ekosistem.js" defer></script>.
   Gagal memuat = markup cadangan tetap tampil. Teks selalu disisipkan sebagai teks (bukan HTML) dan hanya tautan https. */
(function () {
  "use strict";
  var DATA = "https://brainwork-cloud.github.io/brainwork-konten/ekosistem.json";
  var CSS = "https://brainwork-cloud.github.io/brainwork-konten/ekosistem/ekosistem.css";
  var hosts = document.querySelectorAll("[data-ekosistem]");
  if (!hosts.length || !window.fetch) return;

  function aman(u) { return typeof u === "string" && /^https:\/\//.test(u); }
  function teks(v) { return typeof v === "string" && v.trim() ? v : ""; }
  function el(tag, cls, isi) {
    var e = document.createElement(tag);
    if (cls) e.className = cls;
    if (isi) e.textContent = isi;
    return e;
  }
  function tombol(href, label, tipis, dataLabel) {
    var a = el("a", "eko-tombol" + (tipis ? " tipis" : ""), label);
    a.href = href;
    a.setAttribute("data-label", dataLabel);
    return a;
  }

  function render(host, d) {
    var situs = host.getAttribute("data-ekosistem");
    var ps = (d.proyek || []).filter(function (p) {
      return p && p.id !== situs && teks(p.id) && teks(p.nama) && teks(p.deskripsi) && teks(p.tombol) && aman(p.url);
    });
    if (!ps.length) return;
    var j = d.judul || {};
    var h2 = el("h2", "eko-judul", teks(j[situs]) || teks(j.bawaan) || "Proyek lain dari Nopal Brainwork");
    h2.id = "eko-judul-" + situs;
    var ul = el("ul", "eko-daftar");
    ps.forEach(function (p) {
      var li = el("li", "eko-kartu");
      if (teks(p.jenis)) li.appendChild(el("p", "eko-jenis", p.jenis));
      li.appendChild(el("h3", null, p.nama));
      li.appendChild(el("p", "eko-isi", p.deskripsi));
      var cat = p.catatan && teks(p.catatan[situs]);
      if (cat) li.appendChild(el("p", "eko-isi eko-catatan", cat));
      var aksi = el("div", "eko-aksi");
      var a2 = p.aksi2;
      var dua = a2 && aman(a2.url) && teks(a2.teks) && (!Array.isArray(a2.hanya_di) || a2.hanya_di.indexOf(situs) >= 0);
      if (dua) {
        aksi.appendChild(tombol(a2.url, a2.teks, false, teks(a2.label) || "eko-" + p.id + "-2"));
        aksi.appendChild(tombol(p.url, p.tombol, true, "eko-" + p.id));
      } else {
        aksi.appendChild(tombol(p.url, p.tombol, false, "eko-" + p.id));
      }
      li.appendChild(aksi);
      ul.appendChild(li);
    });
    Array.prototype.slice.call(host.children).forEach(function (c) {
      if (c.tagName !== "LINK") host.removeChild(c);
    });
    host.appendChild(h2);
    host.appendChild(ul);
    host.setAttribute("aria-labelledby", h2.id);
  }

  if (!document.querySelector('link[href*="ekosistem.css"]')) {
    var l = document.createElement("link");
    l.rel = "stylesheet";
    l.href = CSS;
    document.head.appendChild(l);
  }
  fetch(DATA, { cache: "no-cache" })
    .then(function (r) { if (!r.ok) throw new Error(r.status); return r.json(); })
    .then(function (d) { Array.prototype.forEach.call(hosts, function (h) { render(h, d); }); })
    .catch(function () { /* markup cadangan tetap tampil */ });
})();
