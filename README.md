# Remove BG + Crop Pas Foto

Tool untuk menghapus background foto (menggunakan `rembg`), memotong objek,
dan menyusunnya menjadi foto pas foto dengan rasio tertentu (3x4, 2x3, 4x6,
paspor, 1x1) di atas background berwarna solid.

Bisa dijalankan dalam **3 mode**: CLI single file, CLI batch, dan **GUI**
(interaktif dengan preview & drag-drop).

---

## 1. Instalasi

```bash
pip install -r requirements.txt
```

`requirements.txt` berisi:

| Paket          | Kegunaan                                   |
|----------------|--------------------------------------------|
| `rembg`        | Menghapus background (model u2net, dll.)   |
| `Pillow`       | Manipulasi gambar (crop, resize, komposisi) |
| `numpy`        | Deteksi bounding box objek                 |
| `onnxruntime`  | Engine inference model rembg               |

> **GPU (opsional):** uninstall `onnxruntime` lalu install `onnxruntime-gpu`
> untuk mempercepat proses (lihat `requirements.txt`).

Model rembg diunduh **otomatis** saat pertama kali dijalankan (sekitar
±170 MB untuk `u2net`).

---

## 2. Cara Menjalankan

### 2a. Mode GUI (interaktif)
<img width="1917" height="1010" alt="Screenshot 2026-08-14 205745" src="https://github.com/user-attachments/assets/b03a6d00-2824-4619-8a32-36ec387b5739" />

```bash
python remove_bg_crop.py gui
```

Fitur GUI:
- **Single File / Batch Folder** (radio button)
- Pilih file atau folder via tombol **Browse**
- **BG Color**: pilih warna lewat color picker, atau klik preset
  (Biru Tua #0B00A3, Biru #0090FF, Merah, Putih, Hijau, Hitam)
- **Rasio Pas Foto**: dropdown preset 3x4, 2x3, 4x6, Paspor, 1x1
- **Target Width (px)**: ukuran lebar final gambar
- **Padding Ratio**: jarak objek dari tepi canvas
- **Model**: pilihan model rembg (u2net, u2netp, u2net_human_seg, dll.)
- **Auto-Enhance**: pencerahan/kontras otomatis
- **Center Object**: posisikan objek di tengah (style foto ijazah)
- **Scale Object**: slider perbesar/perkecil objek (0.2x – 2.0x)
- **Drag-drop**: klik & geser objek di preview untuk posisi manual
- **Live preview**: preview ter-update real-time saat setting diubah
- Tombol **Load & Preview**, **PROSES**, **Reset Position**, **Reset Scale**
- **Progress bar** untuk mode batch

Alur penggunaan GUI:
1. Pilih mode **Single File** atau **Batch Folder**, lalu isi path / Browse.
2. Atur warna background, rasio, ukuran, dsb. sesuai keinginan.
3. (Single) Klik **Load & Preview** untuk melihat hasil, lalu atur posisi/skala objek.
4. Klik **PROSES** untuk menghasilkan file output.

### 2b. Mode CLI — Single File

```bash
python remove_bg_crop.py
```

Membaca `input.jpg` di folder yang sama, lalu menghasilkan `output_3x4.jpg`
(1200x1600 px, background #0B00A3).

> **Penting:** pastikan ada file bernama `input.jpg` di folder yang sama
> sebelum menjalankan. Jika tidak, muncul error `FileNotFoundError`.

### 2c. Mode CLI — Batch

```bash
python remove_bg_crop.py batch <input_dir> <output_dir>
```

Proses **semua gambar** (`.jpg`, `.jpeg`, `.png`, `.webp`, `.bmp`) di
`<input_dir>` dan simpan hasilnya ke `<output_dir>`.

Contoh:

```bash
python remove_bg_crop.py batch putra output
```

Output batch diberi nama `{nama_asli}_{rasio}x{rasio}.jpg`, misal
`foto_3x4.jpg`.

---

## 3. Penggunaan sebagai Library (Python)

Fungsi utama dapat dipanggil langsung dari kode Python:

```python
from remove_bg_crop import remove_bg_and_crop_3x4

# Single gambar
remove_bg_and_crop_3x4(
    input_path="foto.jpg",
    output_path="hasil_3x4.jpg",
    bg_color="#0B00A3",   # warna background (HEX atau tuple RGB)
    target_width=1200,    # -> 1200x1600 px untuk rasio 3:4
    padding_ratio=0.04,   # padding 4%
    model="u2net",
    center_obj=True,      # objek di tengah
    scale_obj=1.0,
    ratio_w=3,
    ratio_h=4,
    enhance=False,
)

# Batch
from remove_bg_crop import batch_process
batch_process(input_dir="folder_in", output_dir="folder_out")
```

### Parameter penting

| Parameter      | Tipe      | Default    | Keterangan                                     |
|----------------|-----------|------------|------------------------------------------------|
| `input_path`   | `str`     | —          | Path file gambar input                         |
| `output_path`  | `str`     | —          | Path file output (`.jpg`/`.png`)               |
| `bg_color`     | `str`/tuple | `"#0B00A3"` | Warna background (HEX atau `(r,g,b)`)        |
| `target_width` | `int`     | `1200`     | Lebar final (px), tinggi mengikuti rasio       |
| `padding_ratio`| `float`   | `0.04`     | Padding di sekitar objek (0.04 = 4%)           |
| `model`        | `str`     | `"u2net"`  | Model rembg                                    |
| `center_obj`   | `bool`    | `True`     | True = objek di tengah canvas                  |
| `scale_obj`    | `float`   | `1.0`      | Skala objek (0.8 = lebih kecil, 1.2 = lebih besar) |
| `custom_offset`| `tuple`   | `None`     | `(x, y)` posisi manual, override center        |
| `ratio_w`/`ratio_h` | `int` | `3`/`4`    | Rasio canvas                                   |
| `enhance`      | `bool`    | `False`    | Auto-enhance brightness/contrast/sharpness     |

---

## 4. Model rembg yang tersedia

| Model                 | Keterangan                          |
|-----------------------|-------------------------------------|
| `u2net`               | Default, akurat untuk umum          |
| `u2netp`              | Versi ringan & lebih cepat          |
| `u2net_human_seg`     | Khusus segmentasi manusia           |
| `isnet-general-use`   | Akurat, bagus untuk foto umum       |
| `isnet-anime`         | Khusus gambar anime                 |
| `silueta`             | Alternatif lain                     |

Model dipilih lewat dropdown **Model** di GUI, atau parameter `model=` di CLI/library.

---

## 5. Rasio pas foto yang tersedia

| Preset               | Rasio | Penggunaan umum          |
|----------------------|-------|--------------------------|
| 3x4 (Ijazah)         | 3:4   | Ijazah, lamaran          |
| 2x3 (KTP/PKNI)       | 2:3   | KTP, dokumen kependudukan|
| 4x6 (Keluarga)       | 4:6   | Foto keluarga           |
| Paspor (2x2 in)      | 1:1   | Paspor                  |
| 1x1 (Kartu)          | 1:1   | Kartu identitas         |

---

## 6. Output & Kualitas

- **JPG**: disimpan dengan `quality=100` + `subsampling=0` (hampir lossless)
- **PNG**: lossless
- Ukuran output mengikuti `target_width` dan rasio, contoh default
  `1200x1600` px untuk rasio 3:4.

---

## 7. Troubleshooting

| Masalah                              | Solusi                                          |
|--------------------------------------|-------------------------------------------------|
| `FileNotFoundError: File input tidak ditemukan` | Pastikan ada `input.jpg` di folder, atau ganti path. |
| Model baru pertama kali berjalan lama | Wajar, model sedang diunduh (±170 MB).          |
| Error `onnxruntime` / tidak ada CUDA  | Instal `onnxruntime` (CPU) saja.                |
| Preview tidak muncul di GUI           | Pilih mode **Single File** lalu klik **Load & Preview**. |

