# Atlas Anatomi Manusia 3D

**Bahasa Indonesia** | [English](README.en.md)

Website pembelajaran anatomi tubuh manusia dengan model 3D interaktif. Pengguna dapat memutar, memperbesar, dan mengeklik langsung struktur tubuh (tulang, otot, saraf, organ, pembuluh darah, dan sistem limfatik), lalu membaca nama (Indonesia, Latin, Inggris), deskripsi, fungsi, hubungan (persarafan, suplai darah, struktur terkait), dan korelasi klinis.

> **Catatan penting:** konten ditulis untuk keperluan belajar dan **bukan pengganti rujukan medis**. Periksa kembali dengan buku teks anatomi sebelum dipakai sebagai bahan ajar resmi.

---

## Daftar isi

1. [Fitur](#fitur)
2. [Cakupan data](#cakupan-data)
3. [Menjalankan dan men-deploy](#menjalankan-dan-men-deploy)
4. [Struktur repositori](#struktur-repositori)
5. [Teknologi yang digunakan](#teknologi-yang-digunakan)
6. [Bagaimana proyek ini dikembangkan](#bagaimana-proyek-ini-dikembangkan)
7. [Format data](#format-data)
8. [Menambah sistem atau struktur baru](#menambah-sistem-atau-struktur-baru)
9. [Keterbatasan yang diketahui](#keterbatasan-yang-diketahui)
10. [Kredit](#kredit)
11. [Lisensi](#lisensi)

---

## Fitur

- **Ruang 3D interaktif**: putar (seret), zoom (scroll atau cubit), geser (klik kanan), reset, dan putar otomatis.
- **Sidebar bertingkat** dengan tab Rangka, Otot, Saraf, dan Organ, dikelompokkan per daerah atau sistem, dilengkapi pencarian.
- **Klik langsung pada model** untuk memilih struktur, dengan label nama saat kursor di atasnya (desktop).
- **Sorot atau Isolasi**: struktur lain dibuat samar atau disembunyikan.
- **Filter sisi** kanan atau kiri tubuh.
- **Konteks rangka**: tulang tampil samar di balik otot, saraf, dan organ supaya letaknya mudah dipahami.
- **Panel deskripsi** berbentuk kartu yang dapat dibuka, ditutup, dan diatur tingginya; sidebar dapat dibuka, ditutup, dan diatur lebarnya.
- **Tema terang dan gelap** dengan latar bintik seperti kanvas diagram.
- **Pemuatan per sistem (lazy loading)**: data model hanya diunduh saat sistem dipilih.
- Dapat digunakan di ponsel (tata letak responsif).

## Cakupan data

Tampilan tubuh utama memakai model Z-Anatomy. Rujukan HuBMAP mempertahankan koordinat sumber. Testis VOXEL-MAN ditampilkan di tengah tampilan tersendiri. Rangka tubuh utama dinonaktifkan pada tampilan rujukan. [Sumber model](data/NOTICE.md)

| Sistem | Item | Mesh | Segitiga | Catatan |
|---|---:|---:|---:|---|
| Rangka | 159 | 277 | 329 rb | Tulang dan tulang rawan; nama ID/Latin/Inggris; deskripsi lengkap |
| Otot | 212 | 462 | 845 rb | Badan otot 3D penuh dari Z-Anatomy (tanpa tempelan entesis); nama ID/Latin untuk otot utama |
| Saraf | 120 | 237 | 78 rb | Saraf utama dan bagian medula spinalis |
| Pernapasan | 48 | 52 | 127 rb | Paru, saluran napas, tulang rawan hidung dan laring kanan-kiri, pleura, dan diafragma |
| Laring dan trakea (HRA) | 11 | 15 | 64 rb | Tulang rawan laring, otot vokalis, cincin trakea, karina, dan bronkus utama |
| Pencernaan | 40 | 46 | 154 rb | Mulut, kelenjar ludah, saluran cerna, hati, empedu, pankreas, dan omentum |
| Reproduksi pria | 10 | 15 | 22 rb | Model sederhana testis dan duktus |
| Testis (Visible Human) | 1 | 1 | 11 rb | Satu testis dewasa dari segmentasi 1 mm |
| Reproduksi perempuan (HRA) | 11 | 19 | 74 rb | Uterus, serviks, ovarium, dan bagian tuba uterina |
| Sistem Urinaria (HRA) | 15 | 81 | 242 rb | Ginjal (termasuk hilus), sistem pengumpul urine, ureter, kandung kemih, dan uretra pria |
| Endokrin | 10 | 13 | 31 rb | Hipotalamus, hipofisis, pineal, tiroid, paratiroid, adrenal, timus |
| Jantung dan pembuluh besar (HRA) | 46 | 51 | 317 rb | Empat ruang, empat katup, septum, pembuluh koroner (termasuk LCx), dan pembuluh besar |
| Pembuluh darah (6 daerah) | 369 | 629 | 3,5 jt | Arteri dan vena per daerah |
| Organ limfatik (HRA) | 2 | 7 | 20 rb | Limpa dan timus |
| Nodus limfatikus (HRA) | 7 | 13 | 254 rb | Bagian-bagian satu nodus |
| Usus halus (HRA) | 7 | 10 | 34 rb | Ampula duodeni, duodenum, sfingter Oddi, papila minor, jejunum, ileum, dan ileum terminal |
| Usus besar (HRA) | 10 | 10 | 34 rb | Sekum, katup ileosekal, apendiks, kolon, fleksura koli, dan rektum |

Tingkat penjelasan:

- **Rinci** (deskripsi, fungsi, persarafan, suplai darah, struktur terkait, korelasi klinis): banyak tulang, organ, dan pembuluh darah utama.
- Sidebar menandai keterangan umum. Entri dengan keterangan terbatas menampilkan lokasi atau kelompoknya.

## Menjalankan dan men-deploy

Halaman memuat `data/*.json` dengan `fetch`, sehingga **tidak bisa dibuka lewat `file://`**. Gunakan server statis apa pun.

### Lokal

```bash
git clone <url-repo-kamu>
cd <nama-repo>
python3 -m http.server 8000
# buka http://localhost:8000
```

### GitHub Pages

1. Push seluruh isi repositori.
2. Settings, lalu Pages.
3. Source: *Deploy from a branch*, branch `main`, folder `/ (root)`.
4. Situs tersedia di `https://<username>.github.io/<repo>/`.

Total data model sekitar 72,3 MiB. Berkas terbesar adalah `atlas_vsKa.json` dengan ukuran sekitar 15,5 MiB.

## Struktur repositori

```
.
├── index.html          # Aplikasi (HTML, CSS, JS dalam satu file)
├── LICENSE             # Lisensi kode (MIT)
├── README.md           # README bahasa Indonesia
├── README.en.md        # README bahasa Inggris
├── ANATOMY-REVIEW.md   # Audit anatomi awal & tindak lanjut
├── data/
│   ├── LICENSE             # Teks lengkap CC BY-SA 4.0 (data dan teks)
│   ├── NOTICE.md           # Asal data, perubahan, dan atribusi
│   ├── atlas_rangka.json
│   ├── atlas_otot.json
│   ├── atlas_saraf.json
│   ├── atlas_organ.json    # pernapasan
│   ├── atlas_cerna.json    # pencernaan
│   ├── atlas_repro.json    # reproduksi pria
│   ├── atlas_reproF.json   # rujukan reproduksi perempuan
│   ├── atlas_testisRef.json # rujukan testis Visible Human
│   ├── atlas_airway.json   # rujukan laring dan trakea
│   ├── atlas_urin.json     # sistem urinaria (HRA)
│   ├── atlas_endo.json     # endokrin
│   ├── atlas_jantung.json  # jantung dan pembuluh besar (HRA)
│   ├── atlas_vsKa.json     # pembuluh: kepala-leher (arteri)
│   ├── atlas_vsKv.json     # pembuluh: kepala-leher (vena)
│   ├── atlas_vsTo.json     # pembuluh: toraks
│   ├── atlas_vsAb.json     # pembuluh: abdomen dan pelvis
│   ├── atlas_vsLe.json     # pembuluh: lengan dan tangan
│   ├── atlas_vsTu.json     # pembuluh: tungkai dan kaki
│   ├── atlas_limfa.json    # limpa dan timus (HRA)
│   ├── atlas_limfonodus.json # nodus limfatikus (HRA)
│   ├── atlas_ususHalus.json  # usus halus (HRA)
│   └── atlas_ususBesar.json  # usus besar (HRA)
├── docs/
│   ├── GEOMETRY-VALIDATION.md  # Laporan validasi geometri 3-tingkat
│   └── research/               # Riset sumber primer (glTF/WebGL, WCAG, TA2/EYD V)
└── tools/              # Skrip Python pengolah dan validasi model offline
```

Nama file data mengikuti kunci layer di `index.html` (`atlas_<kunci>.json`).

## Teknologi yang digunakan

**Aplikasi (front-end)**

- HTML, CSS, dan JavaScript murni (tanpa framework dan tanpa build step), semuanya dalam satu `index.html`.
- [three.js](https://threejs.org/) r128 untuk rendering 3D (`MeshStandardMaterial`, `Raycaster`), dimuat dari CDN cdnjs.
- `OrbitControls` dari paket `three@0.128.0` (CDN jsDelivr) untuk putar, zoom, dan geser.
- CSS variables untuk tema terang dan gelap, `ResizeObserver` untuk menyesuaikan kanvas, Pointer Events untuk seret panel dan klik model.

**Pengolahan data (tools, offline)**

- Python 3 dengan `numpy` (dan `scipy` tersedia) untuk membaca OBJ, membuang duplikat, menyederhanakan mesh, dan mengemas data biner.
- Node.js untuk memeriksa sintaks skrip dan menyusun ulang blok data pada halaman.

**Hosting**

- Versi pengembangan dipublikasikan sebagai halaman web dengan file data terpisah.
- Versi repositori ini memakai jalur relatif `data/…` sehingga cocok untuk GitHub Pages atau server statis lain.

**Pengembangan**

- Proyek ini dikembangkan secara iteratif bersama asisten AI (Claude, Anthropic): perancangan arsitektur, penulisan kode, skrip pengolah model, dan penyusunan teks anatomi. Lihat [Kredit](#kredit) dan [Keterbatasan](#keterbatasan-yang-diketahui) mengenai verifikasi konten.

## Bagaimana proyek ini dikembangkan

Urutan pengerjaan, dari awal sampai sekarang:

1. **Perancangan konten.** Menentukan kerangka materi: sel dan jaringan, sebelas sistem organ, anatomi regional, dan struktur data seragam untuk setiap struktur (nama ID/Latin/Inggris, kategori dan lokasi, deskripsi dan fungsi, hubungan, korelasi klinis).
2. **Prototipe tampilan.** Tata letak dua bagian: sidebar di kiri, ruang 3D dan panel deskripsi di kanan. Versi pertama memakai bentuk 3D prosedural sederhana (silinder dan bola) sebagai pengganti sementara.
3. **Model nyata.** Berkas OBJ Z-Anatomy (seluruh atlas, sekitar 1,3 GB, 4.878 objek) diolah menjadi data yang ringan untuk web.
4. **Penambahan lapisan bertahap**: rangka, lalu otot dan saraf, lalu organ per sistem, lalu pembuluh darah dan limfatik.
5. **Perbaikan antarmuka**: tema terang dan gelap, latar bintik, klik langsung pada model, sorot dan isolasi, filter sisi, panel dapat diatur ukurannya, perbaikan tampilan ponsel.
6. **Pemisahan data per sistem (lazy loading)** agar halaman tetap kecil dan sistem baru bisa ditambah tanpa batas ukuran satu file.

### Alur pengolahan model (`tools/`)

1. **Ekstraksi** — membaca OBJ baris demi baris (streaming) dan menyimpan objek yang dipilih berdasarkan indeks urutan dan pola nama.
2. **Seleksi** — memilih rentang objek untuk tiap sistem. Contoh: tulang dari indeks awal, organ dari rentang viscera, pembuluh dari rentang arteri dan vena.
3. **Pembuangan duplikat** — banyak saluran (ureter, uretra, sebagian bronkus dan duktus, hampir semua pembuluh) tersimpan sebagai dua objek identik di sumbernya. Objek dengan bentuk identik dibuang.
4. **Penyederhanaan** — pada rangka, otot, saraf, pernapasan, dan pencernaan, mesh disederhanakan dengan *vertex clustering* (penggabungan titik pada grid) dengan target jumlah segitiga per objek. Mesh lainnya mempertahankan segitiga sumber. Mesh yang melebihi batas indeks 16-bit dipecah pada batas segitiga.
5. **Kuantisasi dan pengemasan (`ha-mesh-v2`)** — setiap struktur dikemas dengan kuantisasi `uint16` anisotropik per-mesh (serta promosi otomatis ke `float32` IEEE-754 untuk mesh tipis/halus agar tidak menimbulkan segitiga berluas nol, distorsi normal >1,0°, atau pergeseran >5,0 µm), indeks segitiga 16-bit (`<= 65.535` vertex per chunk agar tidak memakai indeks *primitive restart* WebGL 2.0 `65535`), diikat hash generasi `gen`, lalu di-base64 dan ditulis sebagai JSON.
6. **Pengelompokan dan penamaan** — struktur dikelompokkan per sisi, jenis, atau daerah; nama Indonesia (mengacu EYD V / KBBI VI) dan Latin (*Terminologia Anatomica* edisi ke-2 / TA2) ditulis untuk struktur utama.
7. **Penulisan konten** — deskripsi, fungsi, persarafan, suplai darah, struktur terkait, dan korelasi klinis ditulis per struktur atau per kelompok.

### Keputusan desain

- **Satu file HTML tanpa build step** supaya mudah di-host dan dipahami.
- **Data terpisah per sistem** agar halaman awal tetap ringkas (sekitar 400 KB) dan model baru diunduh hanya saat dibutuhkan.
- **Struktur yang menempel pada permukaan struktur lain** (segmen hati, taenia kolon) disembunyikan sampai dipilih supaya tidak berkedip karena permukaan yang berimpit.
- **Selaput tipis** (pleura, mukosa, omentum, mesokolon) ditampilkan transparan dan dikecualikan dari klik di model supaya tidak menghalangi struktur di belakangnya.
- **Pengelompokan daerah pembuluh** mengikuti lokasi anatomi untuk struktur bernama dan memakai posisi untuk mesh lainnya.

## Format data

Setiap `data/atlas_<kunci>.json` memakai format biner *little-endian* berversi `ha-mesh-v2` (penampil tetap mendukung bundel v1 lama secara tervalidasi):

```json
{
  "v": 2,
  "fmt": "ha-mesh-v2",
  "endian": "le",
  "gen": "<ringkasan SHA-256 16-heks yang cocok dengan BL[kunci].gen>",
  "b": "<base64 biner little-endian>",
  "m": {
    "mn": [x, y, z],
    "sc": 1.7,
    "meta": [["Nama_objek.r", jumlahVertex, jumlahSegitiga, offsetByteVertex, offsetByteIndeks, "u16|f32", [ox, oy, oz], [sx, sy, sz]], "..."]
  }
}
```

- Blok biner disusun berurutan dalam urutan byte *little-endian*: semua blok vertex `float32` selaras 4-byte (`12 B/vertex`), diikuti blok vertex `uint16` terkuantisasi per-mesh selaras 2-byte (`6 B/vertex`), lalu blok indeks segitiga `uint16` selaras 2-byte (`6 B/segitiga`, dengan `jumlahVertex <= 65535` agar indeks tidak pernah memakai nilai `65535` yang dicadangkan WebGL 2.0 untuk *primitive restart*).
- Untuk mesh `u16`, posisi dunia dihitung per sumbu sebagai `ox + nilai / 65535 × sx` (didekode eksplisit lewat `DataView.getUint16(..., true)`); mesh `f32` menyimpan koordinat IEEE-754 eksak (`DataView.getFloat32(..., true)`).
- `gen` mengikat bundel geometri JSON dengan pemetaan ordinal sidebar (`BL[kunci].gen`) di `index.html`; penampil memvalidasi versi format, urutan byte, hash generasi, batas koordinat, rentang buffer, indeks segitiga, dan referensi sidebar sebelum menambahkan mesh ke adegan 3D.
- Daftar nama, kelompok, dan teks deskripsi ada di `index.html`:
  - `BL[kunci].g` — kelompok dan item sidebar (`id`, `n` nama utama, `l` Latin, `e` Inggris, `r` daerah, `s` sisi, `p` indeks mesh, `d` kunci deskripsi, `g` bila penjelasan bersifat umum).
  - `DET[kunci]` — teks (`desc`, `fn`, `nerve`, `blood`, `rel`, `clin`).
  - Jalur berkas geometri dibentuk langsung dari kunci layer (`data/atlas_<kunci>.json`).

## Menambah sistem atau struktur baru

1. **Ekstrak dan kemas** objek dari OBJ dengan skrip di `tools/` untuk menghasilkan `data/atlas_<kunci>.json` dan daftar mesh.
2. **Buat kelompok item** dengan `id` (nama dasar objek), `n`, `l`, `e`, `r`, `s`, `p` (indeks mesh), dan `d` (kunci teks).
3. **Tambahkan teks** ke `DET` (enam bidang), atau gunakan kunci umum dengan `g: 1`.
4. **Daftarkan layer** di `index.html`:
   - tambahkan `BL[kunci]`,
   - tambahkan kunci ke `NAMES`, `TITLE`, `LATIN`, `HELP`, dan `EM`,
   - tambahkan opsi di dropdown sistem organ.
5. **Warna**: sesuaikan fungsi `ocol` bila perlu warna khusus per struktur.

> Skrip di `tools/` bersifat referensi: memakai path lokal dan butuh berkas OBJ sumber (tidak disertakan karena ukurannya). Sesuaikan path sebelum menjalankan.

Ikuti [petunjuk impor HuBMAP](data/NOTICE.md#hubmap-reference-models) untuk membuat ulang tampilan rujukan, lalu validasi geometri terhadap sumber GLB dengan `python3 tools/validate_geometry.py <direktori-sumber>` (hasil tercatat di [docs/GEOMETRY-VALIDATION.md](docs/GEOMETRY-VALIDATION.md)).

## Keterbatasan yang diketahui

- Tampilan tubuh utama memakai model pria. Rujukan reproduksi perempuan memakai koordinat Visible Human Female.
- Cakupan yang belum tersedia meliputi kanalis analis, korda tendinea, nodus SA dan AV, perikardium, alveolus, lipatan vokal utuh, serta sebaran nodus dan pembuluh limfe seluruh tubuh. Model testis pria berukuran kecil dan sambungan duktusnya belum lengkap. [Catatan sumber dan pengukuran](data/NOTICE.md)
- **Asimetri model sumber Z-Anatomy**: audit langsung pada berkas sumber `Z-Anatomy/Startup.blend` mengonfirmasi bahwa `Vagus_nerve_(X).l` hanya dimodelkan hingga setinggi T4/arkus aorta (berbeda dari `Vagus_nerve_(X).r` yang turun hingga abdomen), serta pembuluh frenikus (`Superior_phrenic_arteries.r`, `Right_superior_phrenic_vein`, `Inferior_phrenic_artery.r`) hanya tersedia di sisi kanan pada sumber hulu. Otot `Articularis_genus` tidak memiliki mesh badan otot pada sumber Z-Anatomy (hanya bercak origo).
- **Penjelasan umum** untuk sebagian besar cabang pembuluh darah, otot, dan saraf di luar struktur utama. Sebagian nama mengikuti label bahasa Inggris dari sumber.
- **Kualitas model**: rangka, otot (QEM ringan hanya pada lembaran padat >2.200 segitiga melalui [`tools/rebuild_z_anatomy.py`](tools/rebuild_z_anatomy.py)), saraf, pernapasan, dan pencernaan telah disederhanakan; detail mikroskopis berkurang dibanding model mentahnya.
- **Verifikasi konten**: teks anatomi telah ditinjau terhadap sumber rujukan (StatPearls/NCBI Bookshelf, FIPAT *Terminologia Anatomica* TA2, EYD V / KBBI VI), namun belum melalui tinjauan sejawat pakar anatomi/klinisi resmi. Periksa dengan buku teks sebelum dipakai untuk pengajaran formal.
- **Performa**: layer pembuluh kepala-leher (arteri) berukuran sekitar 15,5 MiB dan sekitar 1,34 juta segitiga; pada perangkat lawas bisa terasa berat.

## Kredit

- **[HuBMAP Human Reference Atlas (HRA)](https://humanatlas.io/3d-reference-library)** menyediakan delapan lapisan rujukan berlisensi [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Kredit diberikan kepada **Kristen Browne**, **Heidi Schlehlein**, dan **Arie Kaufman (Stony Brook University)** untuk usus besar. [DOI dan berkas sumber](data/NOTICE.md)
- **[Z-Anatomy](https://github.com/Z-Anatomy/Models-of-human-anatomy)** — sumber model 3D tubuh utama (format Blender/OBJ), dilisensikan [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/).
- **BodyParts3D** — © The Database Center for Life Science (DBCLS), Jepang. Basis data model 3D yang menjadi dasar Z-Anatomy (<https://dbarchive.biosciencedbc.jp/en/bodyparts3d/download.html>).
- **[three.js](https://threejs.org/)** — pustaka rendering 3D (lisensi MIT), termasuk `OrbitControls`.
- **[FIPAT *Terminologia Anatomica* (TA2)](https://fipat.library.dal.ca/ta2/)** — standar internasional penamaan struktur anatomi yang menjadi rujukan penamaan Latin dan Inggris.
- **EYD Edisi V & KBBI VI (Badan Bahasa Kemendikdasmen RI)** — acuan pembakuan ejaan dan serapan istilah medis bahasa Indonesia.
- **Asisten AI (Claude, Anthropic & Antigravity)** — membantu perancangan, pengodean, skrip validasi/pengolah data, serta penulisan dan penyuntingan teks anatomi.

Teks atribusi yang disarankan untuk dicantumkan di situs atau slide:

> Model 3D: BodyParts3D © The Database Center for Life Science, melalui Z-Anatomy (CC BY-SA 4.0), dan HuBMAP Human Reference Atlas (CC BY 4.0 — Kristen Browne, Heidi Schlehlein, Arie Kaufman / Stony Brook University), dikemas untuk web.

## Lisensi

**Ringkasan:** kode aplikasi berlisensi **MIT**; model turunan Z-Anatomy dan teks anatomi berlisensi **CC BY-SA 4.0**. Model rujukan HuBMAP berlisensi **CC BY 4.0**. Berkas lisensi: [`LICENSE`](LICENSE) (MIT, akar repo), [`data/LICENSE`](data/LICENSE) (teks lengkap CC BY-SA 4.0), dan [`data/NOTICE.md`](data/NOTICE.md) (asal data, perubahan, atribusi).

| Komponen | Lisensi | Catatan |
|---|---|---|
| Model 3D turunan Z-Anatomy (`data/`) | **CC BY-SA 4.0** (turunan Z-Anatomy dan BodyParts3D) | Wajib mencantumkan atribusi dan membagikan karya turunan dengan lisensi yang sama (*share-alike*). Model di sini sudah diseleksi, dideduplikasi, dikuantisasi, dan sebagian disederhanakan, sehingga termasuk karya turunan. |
| Kode aplikasi (logika di `index.html`, `tools/`) | **MIT** | Berkas `LICENSE` di akar repo. Hanya mencakup kode, bukan data model atau teks anatomi. |
| Teks deskripsi dan terjemahan (di dalam `index.html`) | **CC BY-SA 4.0** | Selaras dengan lisensi data model. Teks tertanam di `index.html` bersama kode, sehingga file itu memuat dua lisensi: logika kode MIT, teks anatomi CC BY-SA 4.0. |
| Model rujukan HuBMAP | **CC BY 4.0** | Atribusi dan versi sumber tercantum di [data/NOTICE.md](data/NOTICE.md). |
| three.js | MIT | Dimuat dari CDN. |

### Ketentuan lisensi sumber (Z-Anatomy)

Lisensi: [Creative Commons Attribution-ShareAlike 4.0 International (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/).

> With regard to this content, you are licensed to:
> * freely access part or whole of this database, and acquire data;
> * freely redistribute part or whole of the data from this database;
> * and freely create and distribute database and other derivative works based on part or whole of the data from this database, under the license, as long as you comply with the following conditions:
> * You must attribute this database in the manner specified by the author or licensor when distributing part or whole of this database or any derivative work.
> * You must distribute any derivative work based on part or whole of the data from this database under the same license.

Artinya untuk proyek ini:

- Kamu **boleh** mengakses, mendistribusikan ulang, dan membuat karya turunan dari data model.
- **Atribusi wajib** dicantumkan sesuai cara yang ditentukan pemilik lisensi saat mendistribusikan data atau karya turunan. Kutipan di atas tidak merinci format atribusinya, jadi periksa README atau halaman resmi Z-Anatomy untuk format yang diminta. Teks atribusi di bagian [Kredit](#kredit) adalah usulan awal.
- **Karya turunan harus memakai lisensi yang sama** (CC BY-SA 4.0). Folder `data/` di repositori ini adalah karya turunan, sehingga harus dilisensikan CC BY-SA 4.0.

Hal yang perlu diperhatikan:

1. **Lisensi per bagian di sumber (terverifikasi dari `Z-Anatomy/License.txt`).** Untuk BodyParts3D, versi 4.0 berlisensi CC BY 4.0 dan versi lama yang dirujuk Z-Anatomy berlisensi CC BY-SA 2.1 Japan. Z-Anatomy secara keseluruhan berlisensi CC BY-SA 4.0, tetapi mencantumkan beberapa model hulu dengan lisensi terpisah:
   - *Kidney* (Lissie Cowley, CC-BY-NC 4.0): **tidak lagi digunakan** di proyek ini karena Sistem Urinaria telah beralih ke model **HuBMAP (CC BY 4.0)**.
   - *Anatomy of the Inner Ear* (University of Dundee School of Medicine, **CC-BY-NC-SA 4.0**): berlisensi non-komersial. Audit tulang pendengaran (`Malleus`, `Incus`, `Stapes`) dan saraf koklear/vestibular sebelum penggunaan komersial.
   - *Cranial Nerves and Foramina* (University of Dundee, CAHID): CC-BY 4.0.
2. **Lengkapi berkas lisensi.** Pastikan `LICENSE` (MIT) sudah berisi tahun dan nama pemegang hak cipta yang benar, dan `data/LICENSE` berisi teks lengkap CC BY-SA 4.0 yang disalin dari situs Creative Commons.
3. **Pertahankan atribusi** di situs (misalnya pada footer atau panel info) dan di README.

---

*Dibuat untuk tujuan edukasi. Jika menemukan kesalahan anatomi atau penamaan, silakan buka issue atau kirim koreksi.*
