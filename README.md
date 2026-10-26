# Sistem Agen Konten @nopal.brainwork

Versi 3 · 17 Okt 2026. Salinan kerja ada di repo GitHub publik `brainwork-cloud/brainwork-konten`.

## Arsitektur
| Lapisan | Siapa | Tugas |
|---|---|---|
| Otak | 5 scheduled task Claude (cloud, tanpa Mac) | Rencana, naskah, spec JSON, QA, publish IG, analisis |
| Kotak masuk | Folder Google Drive `_inbox` (ID `1sd0X_qci1M688kGryJgqdDug6wMQfCOV`) | Agen cloud tidak bisa push ke GitHub; mereka unggah `<dir>__<ID>__<stamp>.json` ke sini, Actions "Kotak Masuk" (`fetch_inbox.py`) mengambilnya tiap 15 menit dan commit dengan secret `BOT_PAT` supaya render/publish terpicu |
| Mesin | GitHub Actions (gratis, repo publik) | Render carousel & reels motion, edit Reels (transkrip + subtitle + potong jeda + B-roll otomatis), posting Threads |
| Hosting | raw.githubusercontent.com + cdn.jsdelivr.net (`@main`, cache dibersihkan `setup/purge_cdn.sh`) | URL publik gambar/video untuk API Instagram & review Nazwa |
| Kontrol manusia | Google Sheet "Brainwork — Antrian Konten (Agen)" | Nazwa set APPROVED / REVISI / BATAL |

## Jadwal agen (WIB)
| Agen | Jadwal | Butuh Mac? |
|---|---|---|
| 1 Perencana | Minggu 18:52 | Tidak |
| 2 Produser | Senin–Jumat 12:07 | Tidak (sejak 17 Okt; rekaman via Drive) |
| 3a Penerbit IG + mirror FB/Shorts | Tiap hari 10:55, 18:55 | Tidak |
| 3b Antrian Threads | Senin–Jumat 12:37, 16:37 | Tidak |
| 4 Analis | Minggu 18:22 | Tidak |
| 5 Redaktur Portal (Brainwork.id) | Tiap hari 06:23 | Tidak |
| 5 Mirror TikTok/Shorts | manual oleh Nazwa | — |
| 6 Pemantau (COO, hanya membaca, lapor ke Naufal) | Tiap hari 09:37 | Tidak |

## Jalur publish
| Platform | Jalur |
|---|---|
| IG Carousel & Reels | Graph API lewat publish.py (queue/<ID>__instagram.json); Windsor.ai tidak dipakai sejak 27 Okt 2026 |
| Threads | Threads API via GitHub Actions (`publish.py`), diantrikan agen 3b |
| Facebook Page Brainwork.id (mirror IG) | Graph API Page token via GitHub Actions (`publish.py`: foto multi / Reels), diantrikan agen 3a setelah IG terbit |
| YouTube Shorts (mirror Reels) | YouTube Data API via GitHub Actions (`publish.py`), diantrikan agen 3a H+1 |
| TikTok | manual oleh Nazwa dari HP (file `_tiktok.mp4`); API TikTok butuh audit app, ditunda |
| Token | `renew_tokens.py` tiap Senin: refresh token Threads (60 hari) & cek FB/YouTube, status di `tokens/status.txt`; setup sekali: `setup/fb_auth.py`, `setup/yt_auth.py`, lalu `setup/set_secrets.py` |

## Alur Reels
Naufal rekam (kamera/VO saja, tidak pernah rekam layar) → upload ke Drive `Brainwork Rekaman/<ID>/` → Produser tulis `edits/<ID>.json` (+ `make_broll` untuk B-roll layar otomatis) via kotak masuk → Actions `fetch_media.py` → `make_broll.py` → `edit_reel.py` → `aset/<ID>/<ID>.mp4` + `_tiktok.mp4` + cover → Nazwa review di Sheet → terbit.
REVISI: spec dengan ID sama diunggah lagi → md5 spec beda dari `aset/<ID>/.spec.md5` → aset dirender ulang.
Catatan: folder `rekaman/` tidak di-commit; repo publik hanya memuat hasil akhir.

## File
`BRAND.md` · `render_carousel.py` · `render_motion.py` · `edit_reel.py` · `make_broll.py` · `fetch_media.py` · `fetch_inbox.py` · `publish.py` · `.github/workflows/` · `prompts/1-6` · `setup/` (`set_secrets.py --bot-pat`, `git_sync.sh`, `gh_run.py`, `purge_cdn.sh`) · `fonts/`

## Setup yang tersisa
1. Repo publik `brainwork-konten` + sambungkan GitHub di claude.ai + aktifkan GitHub Pages (Settings → Pages → Deploy from branch `main`, folder `/root`).
2. Secrets repo: `THREADS_ACCESS_TOKEN`, `THREADS_USER_ID` (akun @nopal.brainwork, bukan @zenitland).
3. Secrets repo: `YT_CLIENT_ID`, `YT_CLIENT_SECRET`, `YT_REFRESH_TOKEN` (jalankan `setup/yt_auth.py` di Terminal Mac).
4. Chrome "Browser 1" login TikTok @nopal.brainwork; di ekstensi Claude izinkan situs tiktok.com.
