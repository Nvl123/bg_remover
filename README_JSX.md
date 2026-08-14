# Dokumentasi Script Adobe (.jsx)

Dua script ExtendScript untuk otomatisasi di aplikasi Adobe:

1. **`skrip.jsx`** — Script untuk **Adobe Illustrator** (ekspor angka 01–20 jadi PNG)
2. **`skrip_pass.jsx`** — Script untuk **Adobe Photoshop** (batch pas foto)

> **Catatan:** File `.jsx` di sini adalah **ExtendScript** (bahasa scripting Adobe),
> bukan JSX React. Cara menjalankannya berbeda dengan menjalankan kode JavaScript biasa.

---

## Cara menjalankan script .jsx

### Di Illustrator (skrip.jsx)

1. Buka file dokumen di Adobe Illustrator (dengan objek teks terpilih nanti).
2. Klik menu **File → Scripts → Other Script...** (`File > Scripts > Other Script...`)
   dan pilih `skrip.jsx`.
   - Alternatif: salin file ke folder script Illustrator
     (`<folder instalasi>/Presets/en_US/Scripts/` atau
     `C:\Users\<user>\AppData\Roaming\Adobe\Adobe Illustrator <versi>\Presets\<locale>\Scripts\`)
     supaya muncul di menu **Scripts**.
3. Alternatif cepat: pakai **ExtendScript Toolkit (ESTK)** atau editor ExtendScript,
   buka file, lalu tekan tombol *Run*.

### Di Photoshop (skrip_pass.jsx)

1. Buka Photoshop.
2. Klik **File → Scripts → Browse...** (`File > Scripts > Browse...`) dan pilih `skrip_pass.jsx`.
3. Akan muncul dialog untuk memilih folder input, folder output, lalu script berjalan otomatis.

> **Prasyarat skrip_pass.jsx:** Photoshop harus sudah memiliki Action bernama
> **`pass_foto_smk`** di dalam set **`Default Actions`**. Buat/rekam action tersebut
> terlebih dahulu sebelum menjalankan script (lihat bagian 2b).

---

## 1. skrip.jsx — Ekspor Angka PNG (Adobe Illustrator)

### Tujuan

Membuat 20 file PNG dari objek **teks** (TextFrame) yang terpilih, berisi angka
**01 sampai 20**, diekspor satu per satu ke folder yang dipilih.

### Alur kerja

1. Cek dokumen aktif — wajib ada objek teks (`TextFrame`) yang terpilih.
2. Minta user memilih folder penyimpanan.
3. Loop `i = 1..20`:
   - Format angka menjadi 2 digit (`"01"`, `"02"`, ..., `"20"`).
   - Ubah isi teks objek ke angka tersebut.
   - Ekspor sebagai PNG 24-bit transparan berukuran **300%**.
4. Tampilkan alert "Selesai!".

### Cara pakai

1. Di Illustrator, buat **satu objek teks** (misal ketik `01`), lalu **seleksi** objek itu.
2. Jalankan `skrip.jsx` (File → Scripts → Other Script...).
3. Pilih folder tujuan saat dialog muncul.
4. Hasil: 20 file `Angka_01.png` s/d `Angka_20.png` di folder tersebut.

### Detail pengaturan ekspor

| Pengaturan                     | Nilai  | Keterangan                          |
|--------------------------------|--------|-------------------------------------|
| Format                         | PNG24  | PNG 24-bit                          |
| `antiAliasing`                 | `true` | Tepi teks halus                    |
| `transparency`                 | `true` | Background transparan              |
| `artBoardClipping`             | `true` | Dipotong sesuai artboard            |
| `matte`                        | `false`| Tanpa warna matte                  |
| `horizontalScale` / `verticalScale` | `300` | Ukuran ekspor 300%               |

### Penamaan output

- Pola: `Angka_{numStr}.png`
- `numStr` = angka 2 digit: `Angka_01.png`, `Angka_02.png`, dst.

### Syarat / catatan

- Harus ada tepat **1 objek teks terpilih**; jika tidak, script keluar dengan alert.
- Script **mengubah isi teks** objek terpilih menjadi 01–20, jadi pastikan
  objek itu memang teks yang ingin diganti.
- Format numerik di teks memakai pembulatan default Illustrator; jika font
  mendukung tabular figures, angka akan rapi. Tidak ada opsi font di script ini.

---

## 2. skrip_pass.jsx — Batch Pas Foto (Adobe Photoshop)

### Tujuan

Memproses banyak foto sekaligus (pas foto) secara otomatis:

- Buka tiap gambar di folder input.
- Paksa background menjadi **Layer 0** (jika masih `Background`).
- Jalankan **Action Photoshop** `pass_foto_smk`.
- **Flatten** dan simpan ulang sebagai JPEG kualitas tinggi ke folder output.
- Tutup dokumen.

### Alur kerja

1. Minta user pilih **folder input** (folder berisi foto asli).
2. Minta user pilih **folder output** (folder hasil).
3. Kumpulkan file `*.jpg`, `*.jpeg`, `*.png`, `*.tif`, `*.psd` di folder input.
4. Untuk setiap file:
   - **a.** Buka dokumen.
   - **b.** Jika `activeLayer` masih `isBackgroundLayer`, konversi menjadi layer
     biasa bernama "Layer 0" (via Action Descriptor).
   - **c.** Jalankan action `pass_foto_smk` dari set `Default Actions`.
     Jika gagal → tampilkan alert, tutup dokumen tanpa simpan, lalu berhenti.
   - **d.** Simpan otomatis: **flatten** dokumen, simpan sebagai JPEG
     `quality=11`, ekstensi huruf kecil (`Extension.LOWERCASE`).
   - **e.** Tutup dokumen tanpa menyimpan perubahan.
5. Alert "Selesai!" setelah semua file diproses.

### Cara pakai

1. **Buat action `pass_foto_smk`** di panel Actions (Window → Actions):
   - Rekam semua langkah editing pas foto yang diinginkan (crop rasio,
     ganti background, sharpen, dsb.).
   - Simpan dalam set **`Default Actions`** (default Photoshop).
2. Siapkan folder berisi foto asli (bisa 1 atau 100+ file).
3. Jalankan `skrip_pass.jsx` (File → Scripts → Browse...).
4. Pilih folder input → pilih folder output → tunggu proses selesai.

### Detail pengaturan

| Aspek                    | Nilai                        | Keterangan                          |
|--------------------------|------------------------------|-------------------------------------|
| Ekstensi diproses        | `.jpg .jpeg .png .tif .psd`  | Case-insensitive (regex `/i`)       |
| Nama Action              | `pass_foto_smk`              | Harus ada di set `Default Actions`  |
| Set Action               | `Default Actions`            | Set bawaan Photoshop                |
| Kualitas JPEG            | `11`                         | Skala 1–12 (11 = sangat tinggi)     |
| Ekstensi output          | huruf kecil                  | `Extension.LOWERCASE`               |
| Flatten sebelum simpan   | Ya                          | Semua layer digabung jadi satu      |
| Tutup dokumen            | `DONOTSAVECHANGES`           | Setelah tersimpan ke folder output  |

### Penamaan output

- Nama file sama persis dengan file asli, hanya ekstensi diubah ke huruf kecil.
  Contoh: `FOTO.JPG` → disimpan sebagai `foto.jpg` di folder output.

### Syarat / catatan

- **Wajib** action `pass_foto_smk` sudah dibuat di Photoshop, jika tidak script
  berhenti dengan alert `"Gagal pada foto: <nama>..."`.
- Jika folder input kosong / tidak ada gambar, script menampilkan alert dan berhenti.
- Output **selalu JPEG** walaupun inputnya PNG/PSD (karena memakai `saveAs` JPEG).
- Pengaturan background → Layer 0 menggunakan Action Descriptor agar bisa
  otomatis tanpa dialog.

---

## Ringkasan perbedaan

|                         | `skrip.jsx`            | `skrip_pass.jsx`           |
|-------------------------|------------------------|----------------------------|
| Aplikasi                | Adobe Illustrator      | Adobe Photoshop            |
| Mode                    | Single (objek terpilih)| Batch (folder)             |
| Output                  | PNG 24-bit, 300%       | JPEG quality 11            |
| Jumlah file             | 20 (angka 01–20)       | Semua file di folder       |
| Butuh objek/action awal | Objek teks terpilih    | Action `pass_foto_smk`     |
