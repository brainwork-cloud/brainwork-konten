/**
 * Detak Brainwork: pemicu GitHub Actions tepat waktu (17 Nov 2026).
 *
 * Kenapa perlu: jadwal (cron) GitHub Actions di akun brainwork-cloud molor 3-8 jam dan kadang terlewat,
 * jadi posting IG/Threads/portal dan produksi Skalarium telat. Google Apps Script ini memicu workflow
 * lewat API GitHub (workflow_dispatch) tiap 10 menit, dari akun Google Naufal, gratis.
 *
 * Token GitHub TIDAK ditulis di kode ini. Simpan di Project Settings > Script Properties dengan nama GH_TOKEN
 * (fine-grained token, akun brainwork-cloud, repo brainwork-konten + mesin-konten + skalarium-render,
 * izin "Actions: Read and write").
 *
 * Pasang sekali:
 *   1. script.google.com > New project > beri nama "Detak Brainwork" > hapus isi Code.gs > tempel seluruh file ini > Save.
 *   2. Project Settings (ikon gerigi) > Script Properties > Add script property: GH_TOKEN = token tadi > Save.
 *   3. Kembali ke Editor, pilih fungsi "pasang" di bilah atas, klik Run, izinkan akses (Review permissions).
 *      Log harus berbunyi "OK: token berfungsi". Selesai, jalan sendiri tiap 10 menit.
 * Mematikan: jalankan fungsi "lepas" (atau hapus pemicu di menu Triggers).
 */
const OWNER = 'brainwork-cloud';

function detak() {
  const wib = new Date(Date.now() + 7 * 3600 * 1000);
  const jam = wib.getUTCHours();
  const menit = wib.getUTCMinutes();
  const gagal = [];
  const cobaPicu = (repo, wf, inputs) => {
    const kode = picu(repo, wf, inputs);
    if (kode !== 204) gagal.push(repo + '/' + wf + ' -> ' + kode);
  };

  // brainwork-konten: impor kotak masuk Drive (Kotak Masuk otomatis memicu Publish).
  // Malam (00:00-04:59 WIB) cukup sekali per jam.
  if (jam >= 5 || menit < 10) cobaPicu('brainwork-konten', 'inbox.yml');
  // Situs Brainwork.id tiap 30 menit.
  if (menit % 30 < 10) cobaPicu('brainwork-konten', 'situs-portal.yml');
  // Skalarium: produksi harian 04:40 WIB. Aman dipicu ganda (jadwal=ya hanya membuat kekurangan video hari itu).
  if (jam === 4 && menit >= 40 && menit < 50) cobaPicu('mesin-konten', 'produksi.yml', { jadwal: 'ya' });
  // Skalarium: terbit tiap 2 jam, 06:05-22:05 WIB.
  if (jam >= 6 && jam <= 22 && jam % 2 === 0 && menit >= 5 && menit < 15) cobaPicu('mesin-konten', 'terbit.yml');

  // Token kedaluwarsa/salah izin -> lempar galat supaya Google mengirim email pemberitahuan ke pemilik.
  if (gagal.length) throw new Error('Detak Brainwork gagal memicu: ' + gagal.join('; '));
}

function picu(repo, wf, inputs) {
  const token = PropertiesService.getScriptProperties().getProperty('GH_TOKEN');
  if (!token) throw new Error('GH_TOKEN belum diisi di Project Settings > Script Properties');
  const res = UrlFetchApp.fetch(
    'https://api.github.com/repos/' + OWNER + '/' + repo + '/actions/workflows/' + wf + '/dispatches',
    {
      method: 'post',
      contentType: 'application/json',
      muteHttpExceptions: true,
      headers: {
        Authorization: 'Bearer ' + token,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
      },
      payload: JSON.stringify({ ref: 'main', inputs: inputs || {} }),
    }
  );
  const kode = res.getResponseCode();
  if (kode !== 204) console.log(repo + '/' + wf + ': ' + kode + ' ' + res.getContentText().slice(0, 200));
  return kode;
}

function pasang() {
  lepas();
  ScriptApp.newTrigger('detak').timeBased().everyMinutes(10).create();
  return cek();
}

function lepas() {
  ScriptApp.getProjectTriggers()
    .filter((t) => t.getHandlerFunction() === 'detak')
    .forEach((t) => ScriptApp.deleteTrigger(t));
}

function cek() {
  const kode = picu('brainwork-konten', 'inbox.yml');
  const hasil = kode === 204
    ? 'OK: token berfungsi, Kotak Masuk dipicu. Detak jalan tiap 10 menit.'
    : 'GAGAL (' + kode + '): cek token GH_TOKEN dan izinnya (Actions: Read and write untuk brainwork-konten dan mesin-konten).';
  console.log(hasil);
  return hasil;
}
