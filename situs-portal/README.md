# Situs Brainwork.id (otomatis)

Alamat (sementara, di GitHub Pages repo ini): https://brainwork-cloud.github.io/brainwork-konten/brainwork-id/

Situs berita statis untuk portal Brainwork.id. Isinya dibaca otomatis dari repo ini (`portal/*.json`, `queue/*`, `aset/<ID>/`),
jadi **tidak ada yang perlu dikerjakan manual**: begitu agen Redaktur Portal menayangkan berita di Facebook/Instagram dan status
antriannya `posted`, berita itu muncul di situs (maksimal ±30 menit).

| Bagian | Berkas |
|---|---|
| Pembangun (Python, hanya Pillow untuk thumbnail) | `situs-portal/build.py` |
| Gaya (warna dan font mengikuti BRAND.md) | `situs-portal/situs.css` |
| Ikon dan gambar OG (dibuat sekali oleh `buat_ikon.py`) | `situs-portal/ikon/` |
| Jadwal otomatis | `.github/workflows/situs-portal.yml` (tiap 30 menit, manual, dan saat generator diubah) |
| Hasil (jangan diedit tangan; ditulis ulang tiap build) | `brainwork-id/` |

Aturan tayang: hanya konten yang sudah `posted` di Facebook atau Instagram portal. Halaman: beranda, `berita/<judul>-<id>/`,
`kategori/<kategori>/`, `arsip/`, `tentang/`, `feed.xml` (RSS), `sitemap.xml`. Status rilis (uji coba, bertahap, semua user)
dibaca dari kolom status berita dan tidak pernah ditebak: bila tidak jelas, hanya teksnya yang ditampilkan.
Kartu, slide, dan video dimuat langsung dari `aset/<ID>/` (tanpa salinan); hanya thumbnail kecil disimpan di `brainwork-id/media/`.

Menjalankan lokal:
`python3 situs-portal/build.py --konten . --out brainwork-id --origin https://brainwork-cloud.github.io --base /brainwork-konten/brainwork-id/ --aset-base /brainwork-konten/aset/`

Pindah ke domain atau repo sendiri (mis. `brainwork.id`): jalankan build dengan `--origin https://brainwork.id --base /` tanpa
`--aset-base` (kartu dan video ikut disalin ke `media/`), lalu taruh hasilnya di repo Pages yang baru.
