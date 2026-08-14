"""
Remove background dengan rembg, crop (rasio pas foto: 3x4, 2x3, 4x6, paspor),
posisi objek di tengah (center), ganti background jadi #0090FF, dan auto-enhance.

Dependencies:
    pip install rembg pillow numpy onnxruntime
    (atau gunakan gpu: onnxruntime-gpu)

Catatan:
    rembg hanya menghapus background. Untuk memposisikan objek di tengah
    dan memastikan rasio tertentu, kita gunakan Pillow + numpy untuk
    mendeteksi bounding box objek hasil transparan lalu menempatkannya
    pada canvas berwarna.
"""

from pathlib import Path
import numpy as np
from PIL import Image, ImageEnhance, ImageOps
from rembg import remove, new_session


# Warna background target: #0B00A3 (biru tua)
BG_COLOR = "#0B00A3"

# Rasio pas foto default (3x4 untuk ijazah)
RATIO_W, RATIO_H = 3, 4


def hex_to_rgb(hex_color) -> tuple:
    """
    Konversi warna HEX ke tuple RGB.
    Support format: '#0B00A3', '0B00A3', '#0b00a3', atau tuple RGB.

    Returns:
        Tuple (R, G, B) dengan nilai 0-255.
    """
    if isinstance(hex_color, (tuple, list)) and len(hex_color) == 3:
        return tuple(int(c) for c in hex_color)
    hex_str = str(hex_color).lstrip("#").strip()
    if len(hex_str) == 3:
        hex_str = "".join(c * 2 for c in hex_str)
    return tuple(int(hex_str[i:i + 2], 16) for i in (0, 2, 4))

# Preset rasio pas foto umum di Indonesia
RATIO_PRESETS = {
    "3x4 (Ijazah)":     (3, 4),
    "2x3 (KTP/PKNI)":   (2, 3),
    "4x6 (Keluarga)":   (4, 6),
    "Paspor (2x2 in)":  (2, 2),
    "1x1 (Kartu)":      (1, 1),
}


def remove_bg_from_image(
    input_path: str,
    model: str = "u2net",
    session=None,
    alpha_matting: bool = True,
    alpha_matting_foreground_threshold: int = 240,
    alpha_matting_background_threshold: int = 10,
    alpha_matting_erode_size: int = 10,
) -> Image.Image:
    """
    Hapus background gambar -> kembalikan PIL Image RGBA transparan.
    Jika session sudah ada, dipakai ulang (efisien untuk batch/GUI preview).

    Args:
        input_path                            : Path file gambar.
        model                                 : Nama model rembg (diabaikan jika session diberikan).
        session                               : Session rembg yang sudah di-load (opsional).
        alpha_matting                         : Aktifkan alpha matting untuk hasil edge bersih
                                                (menghilangkan shadow/halo di sekitar objek).
        alpha_matting_foreground_threshold    : Threshold foreground (240 = ketat, nilai lebih
                                                rendah = lebih banyak pixel dianggap foreground).
        alpha_matting_background_threshold    : Threshold background (10 = ketat).
        alpha_matting_erode_size              : Ukuran erosi edge (10 = default).

    Returns:
        PIL Image RGBA.
    """
    import io

    input_p = Path(input_path)
    if not input_p.exists():
        raise FileNotFoundError(f"File input tidak ditemukan: {input_path}")

    if session is None:
        session = new_session(model)

    with open(input_p, "rb") as f:
        input_bytes = f.read()

    output_bytes = remove(
        input_bytes,
        session=session,
        alpha_matting=alpha_matting,
        alpha_matting_foreground_threshold=alpha_matting_foreground_threshold,
        alpha_matting_background_threshold=alpha_matting_background_threshold,
        alpha_matting_erode_size=alpha_matting_erode_size,
    )
    return Image.open(io.BytesIO(output_bytes)).convert("RGBA")


def crop_to_object(img_rgba: Image.Image) -> Image.Image:
    """
    Crop gambar RGBA ke bounding box objek (pixel non-transparan) + padding kecil.
    """
    arr = np.array(img_rgba)
    alpha = arr[:, :, 3]
    if alpha.max() == 0:
        raise ValueError("Tidak ada objek terdeteksi (gambar kosong setelah remove bg).")

    ys, xs = np.where(alpha > 0)
    x_min, x_max = xs.min(), xs.max()
    y_min, y_max = ys.min(), ys.max()
    obj_w = x_max - x_min + 1
    obj_h = y_max - y_min + 1

    # padding kecil 2% untuk presisi
    pad = int(max(obj_w, obj_h) * 0.02)
    x_min = max(0, x_min - pad)
    y_min = max(0, y_min - pad)
    x_max = min(arr.shape[1] - 1, x_max + pad)
    y_max = min(arr.shape[0] - 1, y_max + pad)

    return img_rgba.crop((x_min, y_min, x_max + 1, y_max + 1))


def compute_canvas_size(
    obj_w: int,
    obj_h: int,
    padding_ratio: float,
    ratio_w: int = RATIO_W,
    ratio_h: int = RATIO_H,
) -> tuple:
    """
    Hitung ukuran canvas (ratio_w x ratio_h) yang muat untuk objek.
    Return (canvas_w, canvas_h, pad_target).
    """
    pad_target = int(obj_h * padding_ratio)
    canvas_h_tmp = obj_h + 2 * pad_target
    canvas_w_tmp = int(canvas_h_tmp * ratio_w / ratio_h)

    # Jika objek terlalu lebar untuk rasio, scale berdasarkan lebar
    if obj_w > canvas_w_tmp:
        canvas_w_tmp = obj_w + int(obj_w * 0.1)
        canvas_h_tmp = int(canvas_w_tmp * ratio_h / ratio_w)
        if obj_h > canvas_h_tmp - 2 * pad_target:
            pad_target = max(5, (canvas_h_tmp - obj_h) // 2)

    return canvas_w_tmp, canvas_h_tmp, pad_target


def auto_enhance(img: Image.Image, brightness=1.1, contrast=1.15,
                 color=1.05, sharpness=1.1) -> Image.Image:
    """
    Auto-enhance gambar: brightness, contrast, color saturation, sharpness.
    Bekerja pada RGB (alpha dipertahankan jika RGBA).

    Args:
        img        : PIL Image (RGB atau RGBA).
        brightness : Faktor brightness (1.0 = asli, >1 lebih terang).
        contrast   : Faktor contrast (1.0 = asli, >1 lebih kontras).
        color      : Faktor saturasi warna (1.0 = asli).
        sharpness  : Faktor ketajaman (1.0 = asli).

    Returns:
        PIL Image dengan enhance diterapkan.
    """
    if img.mode == "RGBA":
        # Split alpha, enhance RGB, lalu gabung lagi
        r, g, b, a = img.split()
        rgb = Image.merge("RGB", (r, g, b))
        rgb = ImageEnhance.Brightness(rgb).enhance(brightness)
        rgb = ImageEnhance.Contrast(rgb).enhance(contrast)
        rgb = ImageEnhance.Color(rgb).enhance(color)
        rgb = ImageEnhance.Sharpness(rgb).enhance(sharpness)
        r2, g2, b2 = rgb.split()
        return Image.merge("RGBA", (r2, g2, b2, a))
    else:
        img = ImageEnhance.Brightness(img).enhance(brightness)
        img = ImageEnhance.Contrast(img).enhance(contrast)
        img = ImageEnhance.Color(img).enhance(color)
        img = ImageEnhance.Sharpness(img).enhance(sharpness)
        return img


def compose_image(
    obj_crop: Image.Image,
    bg_color: tuple,
    padding_ratio: float = 0.04,
    center_obj: bool = True,
    scale_obj: float = 1.0,
    custom_offset: tuple = None,
    target_width: int = 1200,
    ratio_w: int = RATIO_W,
    ratio_h: int = RATIO_H,
    enhance: bool = False,
) -> Image.Image:
    """
    Tempatkan objek pada canvas (ratio_w x ratio_h) berwarna bg_color.

    Args:
        obj_crop       : PIL Image RGBA (objek yang sudah di-crop).
        bg_color       : Tuple RGB warna background.
        padding_ratio  : Padding di sekitar objek.
        center_obj     : True -> objek di tengah canvas.
        scale_obj      : Skala objek (1.0 = ukuran asli, 0.5 = setengah, dst.).
        custom_offset  : Jika diisi (offset_x, offset_y) dalam koordinat canvas,
                         gunakan posisi ini (drag-drop manual). Mencakup center_obj.
        target_width   : Lebar final (px). Tinggi = target_width * ratio_h / ratio_w.
        ratio_w        : Lebar rasio (default 3).
        ratio_h        : Tinggi rasio (default 4).
        enhance        : True -> terapkan auto-enhance brightness/contrast/sharpness.

    Returns:
        PIL Image RGBA final ukuran target_width x (target_width * ratio_h / ratio_w).
    """
    obj_w = obj_crop.width
    obj_h = obj_crop.height

    # 1. Scale objek jika perlu
    if scale_obj != 1.0 and scale_obj > 0:
        new_w = max(1, int(obj_w * scale_obj))
        new_h = max(1, int(obj_h * scale_obj))
        obj_crop = obj_crop.resize((new_w, new_h), Image.LANCZOS)
        obj_w, obj_h = new_w, new_h

    # 1b. Auto-enhance (opsional)
    if enhance:
        obj_crop = auto_enhance(obj_crop)

    # 2. Hitung canvas size
    canvas_w, canvas_h, pad_target = compute_canvas_size(
        obj_w, obj_h, padding_ratio, ratio_w, ratio_h
    )

    # 3. Buat canvas berwarna bg_color
    canvas_rgba = Image.new("RGBA", (canvas_w, canvas_h), hex_to_rgb(bg_color) + (255,))

    # 4. Tentukan offset (posisi objek di canvas)
    if custom_offset is not None:
        offset_x, offset_y = custom_offset
    elif center_obj:
        offset_x = (canvas_w - obj_w) // 2
        offset_y = (canvas_h - obj_h) // 2
    else:
        offset_x = (canvas_w - obj_w) // 2
        offset_y = pad_target

    # Clamp offset biar objek tidak keluar canvas
    offset_x = max(0, min(offset_x, canvas_w - obj_w))
    offset_y = max(0, min(offset_y, canvas_h - obj_h))

    # 5. Tempel objek ke canvas
    canvas_rgba.paste(obj_crop, (offset_x, offset_y), obj_crop)

    # 6. Resize ke target final
    target_h = int(target_width * ratio_h / ratio_w)
    final_img = canvas_rgba.resize((target_width, target_h), Image.LANCZOS)

    return final_img


def save_image(img: Image.Image, output_path: str, quality: int = 100) -> str:
    """
    Simpan PIL Image ke file.

    - JPG/JPEG: quality 100 + subsampling=0 (no chroma subsampling) -> kualitas maksimal,
                hampir lossless. Untuk benar-benar lossless, pakai PNG.
    - PNG: lossless, tidak ada kompresi lossy.
    """
    out_p = Path(output_path)
    out_p.parent.mkdir(parents=True, exist_ok=True)

    if out_p.suffix.lower() in (".jpg", ".jpeg"):
        img = img.convert("RGB")
        img.save(out_p, "JPEG", quality=quality, subsampling=0, optimize=True)
    else:
        img.save(out_p, "PNG", optimize=True)
    return str(out_p)


def remove_bg_and_crop_3x4(
    input_path: str,
    output_path: str,
    bg_color: tuple = BG_COLOR,
    target_width: int = 1200,
    padding_ratio: float = 0.04,
    model: str = "u2net",
    center_obj: bool = True,
    scale_obj: float = 1.0,
    custom_offset: tuple = None,
    ratio_w: int = RATIO_W,
    ratio_h: int = RATIO_H,
    enhance: bool = False,
) -> str:
    """
    Hapus background gambar dengan rembg, crop dengan rasio (ratio_w x ratio_h),
    posisikan objek di tengah (centered), isi background dengan warna solid,
    dan opsional auto-enhance.

    Args:
        input_path     : Path file gambar input.
        output_path    : Path file output (jpg/png). Pakai .jpg agar ukuran kecil.
        bg_color       : Tuple RGB untuk warna background, default (0, 144, 255) = #0090FF.
        target_width   : Lebar final gambar dalam pixel. Tinggi = target_width * ratio_h / ratio_w.
                         Default 1200 -> 1200x1600 px (rasio 3:4).
        padding_ratio  : Jarak padding di sekitar objek terhadap tinggi canvas (0.04 = 4%).
        model          : Model rembg. Pilihan: 'u2net', 'u2netp', 'u2net_human_seg',
                         'isnet-general-use', 'isnet-anime', 'silueta', dsb.
        center_obj     : Jika True, objek akan ditempatkan persis di tengah canvas.
        scale_obj      : Skala objek (1.0 = asli, 0.8 = lebih kecil, 1.2 = lebih besar).
        custom_offset  : Jika diisi (x, y) -> override posisi center (drag-drop manual).
        ratio_w        : Lebar rasio (default 3).
        ratio_h        : Tinggi rasio (default 4).
        enhance        : True -> terapkan auto-enhance brightness/contrast/sharpness.

    Returns:
        Path file output yang sudah disimpan.

    Workflow:
        1. Load gambar input.
        2. Remove background dengan rembg -> RGBA transparan.
        3. Cari bounding box objek (pixel non-transparan).
        4. Crop objek + sedikit padding.
        5. Hitung ukuran canvas (ratio_w x ratio_h) yang pas agar objek muat.
        6. Tempel objek di canvas (dengan scale, offset, enhance opsional).
        7. Resize ke target_width x (target_width * ratio_h / ratio_w).
        8. Simpan hasil.
    """
    # 1-2. Remove background
    img_rgba = remove_bg_from_image(input_path, model=model)

    # 3-4. Crop ke objek
    obj_crop = crop_to_object(img_rgba)

    # 5-7. Compose: canvas + objek + scale + offset + enhance + resize
    final_img = compose_image(
        obj_crop=obj_crop,
        bg_color=bg_color,
        padding_ratio=padding_ratio,
        center_obj=center_obj,
        scale_obj=scale_obj,
        custom_offset=custom_offset,
        target_width=target_width,
        ratio_w=ratio_w,
        ratio_h=ratio_h,
        enhance=enhance,
    )

    # 8. Simpan
    out_path = save_image(final_img, output_path)

    target_h = int(target_width * ratio_h / ratio_w)
    print(f"[OK] Hasil disimpan ke: {out_path}")
    print(f"     Ukuran final: {target_width} x {target_h} px (rasio {ratio_w}:{ratio_h})")
    rgb = hex_to_rgb(bg_color)
    hex_str = bg_color if isinstance(bg_color, str) else "#{:02X}{:02X}{:02X}".format(*rgb)
    print(f"     Warna BG: {hex_str} / RGB{rgb}")
    if scale_obj != 1.0:
        print(f"     Scale objek: {scale_obj:.2f}x")
    if enhance:
        print(f"     Auto-enhance: ON")
    if custom_offset is not None:
        print(f"     Offset manual: {custom_offset}")
    return out_path


# ----------------------------------------------------------------------
# BATCH PROCESS: proses seluruh folder sekaligus
# ----------------------------------------------------------------------
def batch_process(
    input_dir: str,
    output_dir: str,
    bg_color: tuple = BG_COLOR,
    target_width: int = 1200,
    padding_ratio: float = 0.04,
    model: str = "u2net",
    center_obj: bool = True,
    ratio_w: int = RATIO_W,
    ratio_h: int = RATIO_H,
    enhance: bool = False,
    extensions: tuple = (".jpg", ".jpeg", ".png", ".webp", ".bmp"),
    progress_callback=None,
) -> list:
    """
    Proses semua gambar dalam folder secara batch.

    Args:
        input_dir       : Folder berisi gambar input.
        output_dir      : Folder tujuan output (dibuat otomatis jika belum ada).
        bg_color        : Warna background RGB.
        target_width    : Lebar final (px).
        padding_ratio   : Padding di sekitar objek.
        model           : Model rembg.
        center_obj      : True -> objek di tengah.
        ratio_w         : Lebar rasio (default 3).
        ratio_h         : Tinggi rasio (default 4).
        enhance         : True -> terapkan auto-enhance.
        extensions      : Ekstensi file yang diproses.
        progress_callback : Fungsi callback callback(done, total, current_file).

    Returns:
        List path file output yang berhasil diproses.
    """
    in_dir = Path(input_dir)
    if not in_dir.exists():
        raise FileNotFoundError(f"Folder input tidak ditemukan: {input_dir}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    # Kumpulkan file gambar
    files = [f for f in in_dir.iterdir()
             if f.is_file() and f.suffix.lower() in extensions]

    if not files:
        print(f"[WARN] Tidak ada gambar ditemukan di: {in_dir}")
        return []

    # Load session SEKALI untuk efisiensi (tidak load ulang per gambar)
    print(f"[INFO] Loading model rembg: {model} ...")
    session = new_session(model)
    print(f"[INFO] Memproses {len(files)} file ...")

    results = []
    for i, f in enumerate(files, 1):
        out_name = f.stem + f"_{ratio_w}x{ratio_h}.jpg"
        out_path = out_dir / out_name
        try:
            # Panggil fungsi single tapi dengan session yang sudah ada
            _process_single(
                input_path=str(f),
                output_path=str(out_path),
                bg_color=bg_color,
                target_width=target_width,
                padding_ratio=padding_ratio,
                session=session,
                center_obj=center_obj,
                ratio_w=ratio_w,
                ratio_h=ratio_h,
                enhance=enhance,
            )
            results.append(str(out_path))
            print(f"  [{i}/{len(files)}] OK  -> {out_name}")
        except Exception as e:
            print(f"  [{i}/{len(files)}] FAIL {f.name}: {e}")

        if progress_callback:
            progress_callback(i, len(files), f.name)

    print(f"[DONE] Berhasil: {len(results)}/{len(files)} file.")
    return results


def _process_single(
    input_path: str,
    output_path: str,
    bg_color: tuple,
    target_width: int,
    padding_ratio: float,
    session,
    center_obj: bool,
    scale_obj: float = 1.0,
    custom_offset: tuple = None,
    ratio_w: int = RATIO_W,
    ratio_h: int = RATIO_H,
    enhance: bool = False,
) -> str:
    """
    Internal: versi remove_bg_and_crop_3x4 yang menerima session sudah ada.
    Dipakai oleh batch_process agar tidak load model berulang-ulang.
    """
    img_rgba = remove_bg_from_image(input_path, session=session)
    obj_crop = crop_to_object(img_rgba)
    final_img = compose_image(
        obj_crop=obj_crop,
        bg_color=bg_color,
        padding_ratio=padding_ratio,
        center_obj=center_obj,
        scale_obj=scale_obj,
        custom_offset=custom_offset,
        target_width=target_width,
        ratio_w=ratio_w,
        ratio_h=ratio_h,
        enhance=enhance,
    )
    return save_image(final_img, output_path)


# ----------------------------------------------------------------------
# GUI dengan Tkinter
# ----------------------------------------------------------------------
def launch_gui():
    """
    Buka GUI tkinter untuk remove background + crop pas foto.

    Fitur:
      - Pilih file/folder (single / batch)
      - Pilih warna background (color picker + preset)
      - Multi-crop preset: 3x4 (Ijazah), 2x3 (KTP), 4x6, Paspor 2x2, 1x1
      - Atur ukuran, padding, model
      - Auto-Enhance (brightness/contrast/sharpness)
      - Slider Scale Object (resize objek di canvas)
      - Drag-drop objek di preview untuk posisi custom
      - Live preview (real-time saat slider/color/rasio berubah)
      - Tombol Reset Position & Reset Scale
      - Progress bar untuk batch
    """
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox
    from PIL import ImageTk

    class App:
        # Ukuran preview canvas (3:4)
        PREV_W, PREV_H = 360, 480

        def __init__(self, root):
            self.root = root
            self.root.title("Remove BG + Crop Pas Foto")
            self.root.geometry("900x860")
            self.root.resizable(True, True)

            # ---- Variabel ----
            self.input_path = tk.StringVar()
            self.output_dir = tk.StringVar()
            self.bg_color = BG_COLOR  # hex string, e.g. "#0B00A3"
            self.target_width = tk.IntVar(value=1200)
            self.padding_ratio = tk.DoubleVar(value=0.04)
            self.model = tk.StringVar(value="u2net")
            self.center_obj = tk.BooleanVar(value=True)
            self.batch_mode = tk.BooleanVar(value=False)
            self.scale_obj = tk.DoubleVar(value=1.0)
            self.ratio_preset = tk.StringVar(value="3x4 (Ijazah)")
            self.enhance = tk.BooleanVar(value=False)

            # State internal untuk drag-drop & live preview
            self.preview_img = None          # ref ImageTk (jangan di-GC)
            self.obj_crop = None             # PIL RGBA objek hasil remove bg + crop
            self.session = None              # session rembg (di-cache)
            self.current_canvas_size = None  # (canvas_w, canvas_h) koord. canvas asli
            self.custom_offset = None        # (offset_x, offset_y) di koord. canvas asli
            self.dragging = False
            self.drag_start = None           # (x, y) awal drag di koord. preview
            self._current_offset = (0, 0)    # offset saat ini (di-update oleh _update_preview)
            self._current_obj_size = (0, 0)  # ukuran objek saat ini (setelah scale)
            self._drag_base_offset = (0, 0)  # base offset saat mulai drag

            self._build_ui()

        # ============================================================
        # BUILD UI
        # ============================================================
        def _build_ui(self):
            pad = {"padx": 8, "pady": 4}

            # ===== Input =====
            in_frame = ttk.LabelFrame(self.root, text="Input")
            in_frame.pack(fill="x", **pad)

            ttk.Radiobutton(in_frame, text="Single File",
                            variable=self.batch_mode, value=False,
                            command=self._toggle_mode).grid(row=0, column=0, sticky="w", padx=5, pady=5)
            ttk.Radiobutton(in_frame, text="Batch Folder",
                            variable=self.batch_mode, value=True,
                            command=self._toggle_mode).grid(row=0, column=1, sticky="w", padx=5, pady=5)

            ttk.Label(in_frame, text="Path:").grid(row=1, column=0, sticky="w", padx=5)
            ttk.Entry(in_frame, textvariable=self.input_path, width=70).grid(row=1, column=1, columnspan=2, sticky="we", padx=5)
            ttk.Button(in_frame, text="Browse", command=self._browse_input).grid(row=1, column=3, padx=5)
            in_frame.columnconfigure(1, weight=1)

            # ===== Output =====
            out_frame = ttk.LabelFrame(self.root, text="Output")
            out_frame.pack(fill="x", **pad)

            ttk.Label(out_frame, text="Folder:").grid(row=0, column=0, sticky="w", padx=5)
            ttk.Entry(out_frame, textvariable=self.output_dir, width=70).grid(row=0, column=1, columnspan=2, sticky="we", padx=5)
            ttk.Button(out_frame, text="Browse", command=self._browse_output).grid(row=0, column=3, padx=5)
            out_frame.columnconfigure(1, weight=1)

            # ===== Settings =====
            set_frame = ttk.LabelFrame(self.root, text="Settings")
            set_frame.pack(fill="x", **pad)

            # Warna
            ttk.Label(set_frame, text="BG Color:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
            self.color_btn = tk.Button(set_frame, text="#0B00A3", bg="#0B00A3", fg="white",
                                       command=self._pick_color, relief="flat", width=10)
            self.color_btn.grid(row=0, column=1, sticky="w", padx=5)

            # Target width
            ttk.Label(set_frame, text="Target Width (px):").grid(row=0, column=2, sticky="w", padx=5)
            ttk.Spinbox(set_frame, from_=300, to=4000, increment=100,
                        textvariable=self.target_width, width=8).grid(row=0, column=3, padx=5)

            # Padding
            ttk.Label(set_frame, text="Padding Ratio:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
            ttk.Spinbox(set_frame, from_=0.0, to=0.3, increment=0.01,
                        textvariable=self.padding_ratio, format="%.2f", width=8).grid(row=1, column=1, padx=5)

            # Model
            ttk.Label(set_frame, text="Model:").grid(row=1, column=2, sticky="w", padx=5)
            models = ["u2net", "u2netp", "u2net_human_seg", "isnet-general-use", "isnet-anime", "silueta"]
            ttk.Combobox(set_frame, textvariable=self.model, values=models,
                         state="readonly", width=18).grid(row=1, column=3, padx=5)

            # Rasio preset (dropdown)
            ttk.Label(set_frame, text="Rasio Pas Foto:").grid(row=2, column=0, sticky="w", padx=5, pady=5)
            self.ratio_combo = ttk.Combobox(set_frame, textvariable=self.ratio_preset,
                                            values=list(RATIO_PRESETS.keys()),
                                            state="readonly", width=15)
            self.ratio_combo.grid(row=2, column=1, sticky="w", padx=5)
            self.ratio_combo.bind("<<ComboboxSelected>>", lambda e: self._on_ratio_change())

            # Auto-enhance checkbox
            ttk.Checkbutton(set_frame, text="Auto-Enhance (brightness/contrast)",
                            variable=self.enhance,
                            command=self._update_preview).grid(row=2, column=2, columnspan=2, sticky="w", padx=5)

            # Center object checkbox
            ttk.Checkbutton(set_frame, text="Center Object (foto ijazah)",
                            variable=self.center_obj,
                            command=self._on_center_toggle).grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5)

            # Scale Object slider
            ttk.Label(set_frame, text="Scale Object:").grid(row=4, column=0, sticky="w", padx=5, pady=5)
            scale_frame = ttk.Frame(set_frame)
            scale_frame.grid(row=4, column=1, columnspan=3, sticky="we", padx=5)
            self.scale_slider = ttk.Scale(scale_frame, from_=0.2, to=2.0,
                                          variable=self.scale_obj,
                                          command=self._on_scale_change)
            self.scale_slider.pack(side="left", fill="x", expand=True)
            self.scale_label = ttk.Label(scale_frame, text="1.00x", width=6)
            self.scale_label.pack(side="left", padx=5)
            ttk.Button(scale_frame, text="Reset Scale", width=10,
                       command=self._reset_scale).pack(side="left", padx=5)

            # Preset warna
            ttk.Label(set_frame, text="Preset:").grid(row=5, column=0, sticky="w", padx=5, pady=2)
            preset_frame = ttk.Frame(set_frame)
            preset_frame.grid(row=5, column=1, columnspan=3, sticky="w", padx=5)
            presets = [
                ("Biru Tua #0B00A3", "#0B00A3"),
                ("Biru #0090FF",     "#0090FF"),
                ("Merah",            "#FF0000"),
                ("Putih",            "#FFFFFF"),
                ("Hijau",            "#00FF00"),
                ("Hitam",            "#000000"),
            ]
            for name, hexc in presets:
                rgb = hex_to_rgb(hexc)
                b = tk.Button(preset_frame, text=name, bg=hexc,
                              fg="white" if sum(rgb) < 384 else "black",
                              relief="flat", width=14,
                              command=lambda h=hexc: self._set_color(h))
                b.pack(side="left", padx=2)

            set_frame.columnconfigure(1, weight=1)

            # ===== Tombol Preview & Proses =====
            btn_frame = ttk.Frame(self.root)
            btn_frame.pack(fill="x", **pad)

            self.preview_btn = ttk.Button(btn_frame, text="Load & Preview",
                                          command=self._load_and_preview)
            self.preview_btn.pack(side="left", padx=5)

            self.process_btn = ttk.Button(btn_frame, text="PROSES", command=self._process)
            self.process_btn.pack(side="left", padx=5)

            self.reset_pos_btn = ttk.Button(btn_frame, text="Reset Position",
                                            command=self._reset_position)
            self.reset_pos_btn.pack(side="left", padx=5)

            self.status_label = ttk.Label(btn_frame, text="Siap. Load gambar untuk mulai.")
            self.status_label.pack(side="left", padx=10)

            # ===== Progress =====
            prog_frame = ttk.Frame(self.root)
            prog_frame.pack(fill="x", **pad)
            self.progress = ttk.Progressbar(prog_frame, mode="determinate", length=400)
            self.progress.pack(side="left", padx=5, fill="x", expand=True)
            self.progress_label = ttk.Label(prog_frame, text="0%")
            self.progress_label.pack(side="left", padx=5)

            # ===== Preview (canvas untuk drag-drop) =====
            prev_frame = ttk.LabelFrame(self.root, text="Preview (klik-drag objek untuk atur posisi)")
            prev_frame.pack(fill="both", expand=True, **pad)

            self.canvas = tk.Canvas(prev_frame, width=self.PREV_W, height=self.PREV_H,
                                    bg="#dddddd", highlightthickness=1,
                                    highlightbackground="#888888")
            self.canvas.pack(fill="both", expand=True, padx=10, pady=10)

            # Event drag-drop
            self.canvas.bind("<ButtonPress-1>", self._on_drag_start)
            self.canvas.bind("<B1-Motion>", self._on_drag_motion)
            self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

            # Hint teks di canvas
            self.canvas_hint = self.canvas.create_text(
                self.PREV_W // 2, self.PREV_H // 2,
                text="Klik 'Load & Preview' untuk memuat gambar",
                fill="#666666", font=("Arial", 10)
            )

        # ============================================================
        # METHODS
        # ============================================================
        def _toggle_mode(self):
            self.input_path.set("")

        def _browse_input(self):
            if self.batch_mode.get():
                d = filedialog.askdirectory(title="Pilih Folder Input")
                if d:
                    self.input_path.set(d)
                    if not self.output_dir.get():
                        self.output_dir.set(str(Path(d) / "output"))
            else:
                f = filedialog.askopenfilename(
                    title="Pilih File Gambar",
                    filetypes=[("Images", "*.jpg *.jpeg *.png *.webp *.bmp")]
                )
                if f:
                    self.input_path.set(f)
                    if not self.output_dir.get():
                        self.output_dir.set(str(Path(f).parent / "output"))

        def _browse_output(self):
            d = filedialog.askdirectory(title="Pilih Folder Output")
            if d:
                self.output_dir.set(d)

        def _pick_color(self):
            from tkinter import colorchooser
            color = colorchooser.askcolor(title="Pilih Warna Background",
                                          initialcolor=self.bg_color)
            if color and color[1]:
                hexc = color[1].upper()
                self.bg_color = hexc
                rgb = hex_to_rgb(hexc)
                self.color_btn.config(text=hexc, bg=hexc,
                                      fg="white" if sum(rgb) < 384 else "black")
                self._update_preview()

        def _set_color(self, hexc):
            hexc = hexc.upper()
            self.bg_color = hexc
            rgb = hex_to_rgb(hexc)
            self.color_btn.config(text=hexc, bg=hexc,
                                  fg="white" if sum(rgb) < 384 else "black")
            self._update_preview()

        # ----- Live preview -----
        def _get_or_create_session(self):
            if self.session is None:
                self._set_status("Loading model rembg...")
                self.root.update_idletasks()
                self.session = new_session(self.model.get())
            return self.session

        def _load_and_preview(self):
            """Load gambar, remove bg, lalu tampilkan preview (di background thread)."""
            inp = self.input_path.get().strip()
            if not inp:
                messagebox.showerror("Error", "Pilih file input dulu (mode Single).")
                return
            if self.batch_mode.get():
                messagebox.showinfo("Info", "Preview hanya untuk mode Single File. "
                                           "Untuk batch, langsung klik PROSES.")
                return

            # Disable tombol, kasih feedback
            self.process_btn.config(state="disabled")
            self.preview_btn.config(state="disabled")
            self.root.config(cursor="watch")
            self._set_status("Memproses remove background... (mohon tunggu)")

            # Load session sinkron dulu (sekali saja), lalu proses remove di thread
            try:
                session = self._get_or_create_session()
            except Exception as e:
                messagebox.showerror("Error", f"Gagal load model: {e}")
                self._set_status(f"Error: {e}")
                self.process_btn.config(state="normal")
                self.preview_btn.config(state="normal")
                self.root.config(cursor="")
                return

            # Jalankan remove bg di thread terpisah biar GUI tidak freeze
            import threading

            def worker():
                try:
                    img_rgba = remove_bg_from_image(inp, session=session)
                    self.obj_crop = crop_to_object(img_rgba)

                    # Update UI harus di main thread
                    self.root.after(0, self._on_preview_ready)
                except Exception as e:
                    err = str(e)
                    self.root.after(0, lambda: self._on_preview_error(err))

            t = threading.Thread(target=worker, daemon=True)
            t.start()

        def _on_preview_ready(self):
            """Dipanggil setelah remove bg selesai (di main thread)."""
            # Reset state
            self.scale_obj.set(1.0)
            self.scale_label.config(text="1.00x")
            self.custom_offset = None
            self.center_obj.set(True)

            self._update_preview()
            self._set_status("Preview siap. Drag objek untuk atur posisi, "
                             "atau gerakkan slider untuk scale.")
            self.process_btn.config(state="normal")
            self.preview_btn.config(state="normal")
            self.root.config(cursor="")

        def _on_preview_error(self, err):
            """Dipanggil jika remove bg gagal (di main thread)."""
            messagebox.showerror("Error", err)
            self._set_status(f"Error: {err}")
            self.process_btn.config(state="normal")
            self.preview_btn.config(state="normal")
            self.root.config(cursor="")

        def _update_preview(self):
            """Render ulang preview dari self.obj_crop + setting saat ini."""
            if self.obj_crop is None:
                return

            # Ambil rasio dari preset
            rw, rh = RATIO_PRESETS.get(self.ratio_preset.get(), (RATIO_W, RATIO_H))

            # Hitung canvas size asli (full-res) berdasarkan objek + scale
            scale = self.scale_obj.get()
            obj = self.obj_crop
            obj_w = max(1, int(obj.width * scale))
            obj_h = max(1, int(obj.height * scale))

            # Auto-enhance jika aktif
            if self.enhance.get():
                obj = auto_enhance(obj)

            canvas_w, canvas_h, pad_target = compute_canvas_size(
                obj_w, obj_h, self.padding_ratio.get(), rw, rh
            )
            self.current_canvas_size = (canvas_w, canvas_h)

            # Tentukan offset
            if self.custom_offset is not None:
                offset_x, offset_y = self.custom_offset
            elif self.center_obj.get():
                offset_x = (canvas_w - obj_w) // 2
                offset_y = (canvas_h - obj_h) // 2
            else:
                offset_x = (canvas_w - obj_w) // 2
                offset_y = pad_target

            # Clamp
            offset_x = max(0, min(offset_x, canvas_w - obj_w))
            offset_y = max(0, min(offset_y, canvas_h - obj_h))

            # Simpan offset current (untuk drag-drop reference)
            self._current_offset = (offset_x, offset_y)
            self._current_obj_size = (obj_w, obj_h)

            # Render preview kecil (PREV_W x PREV_H) untuk performa
            prev_w, prev_h = self.PREV_W, self.PREV_H
            canvas_img = Image.new("RGBA", (canvas_w, canvas_h), hex_to_rgb(self.bg_color) + (255,))
            obj_scaled = obj.resize((obj_w, obj_h), Image.LANCZOS) if scale != 1.0 else obj
            canvas_img.paste(obj_scaled, (offset_x, offset_y), obj_scaled)
            canvas_img = canvas_img.resize((prev_w, prev_h), Image.LANCZOS)

            # Tampilkan ke canvas tkinter
            self.preview_img = ImageTk.PhotoImage(canvas_img)
            self.canvas.delete("all")
            self.canvas.create_image(prev_w // 2, prev_h // 2, image=self.preview_img)

            # Gambar border objek (visual feedback saat drag)
            self._draw_obj_border(offset_x, offset_y, obj_w, obj_h, canvas_w, canvas_h)

        def _draw_obj_border(self, offset_x, offset_y, obj_w, obj_h, canvas_w, canvas_h):
            """Gambar kotak dashed di sekitar objek (scale ke preview)."""
            sx = self.PREV_W / canvas_w
            sy = self.PREV_H / canvas_h
            x1 = offset_x * sx
            y1 = offset_y * sy
            x2 = (offset_x + obj_w) * sx
            y2 = (offset_y + obj_h) * sy
            self.canvas.create_rectangle(x1, y1, x2, y2, outline="#00FF00",
                                         dash=(4, 4), width=1)

        # ----- Scale slider -----
        def _on_scale_change(self, _=None):
            val = self.scale_obj.get()
            self.scale_label.config(text=f"{val:.2f}x")
            # Saat scale berubah, reset custom offset (karena ukuran objek beda)
            self.custom_offset = None
            self._update_preview()

        def _reset_scale(self):
            self.scale_obj.set(1.0)
            self.scale_label.config(text="1.00x")
            self.custom_offset = None
            self._update_preview()

        # ----- Center toggle -----
        def _on_center_toggle(self):
            if self.center_obj.get():
                self.custom_offset = None
            self._update_preview()

        # ----- Rasio change -----
        def _on_ratio_change(self):
            """Dipanggil saat dropdown rasio diganti. Update preview + status."""
            preset = self.ratio_preset.get()
            if preset in RATIO_PRESETS:
                rw, rh = RATIO_PRESETS[preset]
                # Update ukuran preview canvas sesuai rasio (max 480 tinggi)
                if rh >= rw:
                    self.PREV_H = 480
                    self.PREV_W = int(480 * rw / rh)
                else:
                    self.PREV_W = 480
                    self.PREV_H = int(480 * rh / rw)
                self.canvas.config(width=self.PREV_W, height=self.PREV_H)
                self._set_status(f"Rasio diubah ke {preset} ({rw}:{rh})")
            self.custom_offset = None
            self._update_preview()

        # ----- Reset position -----
        def _reset_position(self):
            self.custom_offset = None
            self.center_obj.set(True)
            self._update_preview()
            self._set_status("Posisi direset ke center.")

        # ----- Drag-drop -----
        def _on_drag_start(self, event):
            if self.obj_crop is None or self.current_canvas_size is None:
                return
            self.dragging = True
            self.drag_start = (event.x, event.y)
            # Simpan base offset (posisi sebelum drag) sebagai referensi
            self._drag_base_offset = self._current_offset
            # Saat mulai drag, matikan center agar offset custom dipakai
            if self.center_obj.get():
                self.center_obj.set(False)
                # init custom_offset dari posisi center saat ini
                self.custom_offset = self._current_offset
            self.canvas.config(cursor="fleur")

        def _on_drag_motion(self, event):
            if not self.dragging or self.current_canvas_size is None:
                return

            canvas_w, canvas_h = self.current_canvas_size
            sx = canvas_w / self.PREV_W
            sy = canvas_h / self.PREV_H

            dx = (event.x - self.drag_start[0]) * sx
            dy = (event.y - self.drag_start[1]) * sy

            obj_w, obj_h = self._current_obj_size
            base_x, base_y = self._drag_base_offset
            new_x = base_x + int(dx)
            new_y = base_y + int(dy)

            # Clamp
            new_x = max(0, min(new_x, canvas_w - obj_w))
            new_y = max(0, min(new_y, canvas_h - obj_h))

            self.custom_offset = (new_x, new_y)
            self.drag_start = (event.x, event.y)
            self._drag_base_offset = (new_x, new_y)
            self._update_preview()

        def _on_drag_end(self, event):
            self.dragging = False
            self.canvas.config(cursor="")

        # ----- Proses -----
        def _process(self):
            inp = self.input_path.get().strip()
            out = self.output_dir.get().strip()
            if not inp:
                messagebox.showerror("Error", "Pilih file/folder input dulu.")
                return
            if not out:
                messagebox.showerror("Error", "Pilih folder output dulu.")
                return

            # Ambil setting sekali sebelum thread
            rw, rh = RATIO_PRESETS.get(self.ratio_preset.get(), (RATIO_W, RATIO_H))
            settings = {
                "inp": inp,
                "out": out,
                "bg_color": self.bg_color,
                "target_width": self.target_width.get(),
                "padding_ratio": self.padding_ratio.get(),
                "model": self.model.get(),
                "center_obj": self.center_obj.get(),
                "scale_obj": self.scale_obj.get(),
                "custom_offset": self.custom_offset,
                "rw": rw,
                "rh": rh,
                "enhance": self.enhance.get(),
                "obj_crop": self.obj_crop,
                "batch": self.batch_mode.get(),
            }

            self.process_btn.config(state="disabled")
            self.preview_btn.config(state="disabled")
            self.root.config(cursor="watch")
            self._set_status("Memproses... (mohon tunggu)")

            import threading

            def worker():
                try:
                    if settings["batch"]:
                        def cb(done, total, fname):
                            self.root.after(0, lambda d=done, t=total, f=fname: self._update_batch_progress(d, t, f))

                        results = batch_process(
                            input_dir=settings["inp"],
                            output_dir=settings["out"],
                            bg_color=settings["bg_color"],
                            target_width=settings["target_width"],
                            padding_ratio=settings["padding_ratio"],
                            model=settings["model"],
                            center_obj=settings["center_obj"],
                            ratio_w=settings["rw"],
                            ratio_h=settings["rh"],
                            enhance=settings["enhance"],
                            progress_callback=cb,
                        )
                        self.root.after(0, lambda: self._on_process_done(
                            f"Selesai. {len(results)} file berhasil.", f"Berhasil memproses {len(results)} file.\nOutput: {settings['out']}"))
                    else:
                        out_path = Path(settings["out"]) / (Path(settings["inp"]).stem + f"_{settings['rw']}x{settings['rh']}.jpg")

                        if settings["obj_crop"] is not None:
                            final_img = compose_image(
                                obj_crop=settings["obj_crop"],
                                bg_color=settings["bg_color"],
                                padding_ratio=settings["padding_ratio"],
                                center_obj=settings["center_obj"],
                                scale_obj=settings["scale_obj"],
                                custom_offset=settings["custom_offset"],
                                target_width=settings["target_width"],
                                ratio_w=settings["rw"],
                                ratio_h=settings["rh"],
                                enhance=settings["enhance"],
                            )
                            save_image(final_img, str(out_path))
                        else:
                            remove_bg_and_crop_3x4(
                                input_path=settings["inp"],
                                output_path=str(out_path),
                                bg_color=settings["bg_color"],
                                target_width=settings["target_width"],
                                padding_ratio=settings["padding_ratio"],
                                model=settings["model"],
                                center_obj=settings["center_obj"],
                                scale_obj=settings["scale_obj"],
                                custom_offset=settings["custom_offset"],
                                ratio_w=settings["rw"],
                                ratio_h=settings["rh"],
                                enhance=settings["enhance"],
                            )

                        target_h = int(settings["target_width"] * settings["rh"] / settings["rw"])
                        msg = f"Selesai: {out_path.name} ({settings['target_width']}x{target_h})"
                        self.root.after(0, lambda: self._on_process_done(msg, f"File disimpan:\n{out_path}"))
                except Exception as e:
                    err = str(e)
                    self.root.after(0, lambda: self._on_process_error(err))

            t = threading.Thread(target=worker, daemon=True)
            t.start()

        def _update_batch_progress(self, done, total, fname):
            self.progress["maximum"] = total
            self.progress["value"] = done
            pct = int(done / total * 100) if total else 0
            self.progress_label.config(text=f"{pct}%  ({done}/{total})")
            self._set_status(f"Memproses: {fname}")

        def _on_process_done(self, status_msg, info_msg):
            self._set_status(status_msg)
            messagebox.showinfo("Selesai", info_msg)
            self.process_btn.config(state="normal")
            self.preview_btn.config(state="normal")
            self.root.config(cursor="")

        def _on_process_error(self, err):
            messagebox.showerror("Error", err)
            self._set_status(f"Error: {err}")
            self.process_btn.config(state="normal")
            self.preview_btn.config(state="normal")
            self.root.config(cursor="")

        def _set_status(self, text):
            self.status_label.config(text=text)

    # Jalankan app
    root = tk.Tk()
    app = App(root)
    root.mainloop()


# ----------------------------------------------------------------------
# Contoh pemakaian
# ----------------------------------------------------------------------
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "gui":
        # jalankan GUI
        launch_gui()
    elif len(sys.argv) > 1 and sys.argv[1] == "batch":
        # batch via CLI: python remove_bg_crop.py batch <input_dir> <output_dir>
        in_dir = sys.argv[2]
        out_dir = sys.argv[3]
        batch_process(input_dir=in_dir, output_dir=out_dir)
    else:
        # default: single file
        INPUT_IMAGE = "input.jpg"
        OUTPUT_IMAGE = "output_3x4.jpg"

        remove_bg_and_crop_3x4(
            input_path=INPUT_IMAGE,
            output_path=OUTPUT_IMAGE,
            bg_color="#0B00A3",      # biru tua (HEX)
            target_width=1200,        # -> 1200 x 1600 px
            padding_ratio=0.04,       # padding 4% di sekitar objek
            model="u2net",            # model rembg
            center_obj=True,          # objek di tengah (foto ijazah style)
            scale_obj=1.0,            # skala objek
            ratio_w=3,                # lebar rasio (3x4)
            ratio_h=4,                # tinggi rasio
            enhance=False,            # auto-enhance off
        )
