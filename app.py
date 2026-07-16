# -*- coding: utf-8 -*-
"""
app.py
------
Backend web lokal untuk Sistem Rekapitulasi Absensi Otomatis
Bidang Daskrimti - Kejaksaan Tinggi Jawa Tengah.

Menjalankan:
    python app.py
lalu buka http://127.0.0.1:5000 di browser.
"""

import os
import hashlib
import threading
import time
from datetime import datetime

from flask import Flask, render_template, request, jsonify, send_file
import pandas as pd

from extractor import ekstrak_pdf
from rekap_resmi import tulis_sheet_rekap_resmi

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(OUTPUT_DIR, exist_ok=True)

app = Flask(__name__)
# Batas ukuran total unggahan sekaligus. Dinaikkan ke 2 GB karena untuk ~380
# file PDF absensi (apalagi jika sebagian hasil scan/gambar) 300 MB berisiko
# kurang. Sesuaikan lagi angka ini jika perlu.
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # 2 GB


@app.errorhandler(413)
def terlalu_besar(e):
    """Pesan error yang rapi (bukan halaman error mentah bawaan Flask)
    saat total ukuran file yang diunggah melebihi batas di atas."""
    batas_mb = app.config["MAX_CONTENT_LENGTH"] // (1024 * 1024)
    return jsonify({
        "ok": False,
        "pesan": (
            f"Total ukuran file yang diunggah melebihi batas ({batas_mb} MB). "
            "Coba unggah dalam beberapa kelompok/batch yang lebih kecil, "
            "atau naikkan batas MAX_CONTENT_LENGTH di app.py."
        ),
    }), 413

# Status proses disimpan di memori (cukup untuk pemakaian lokal 1 pengguna).
# Mendukung unggah & proses BERTAHAP: file baru bisa ditambahkan kapan saja
# dan diproses menyusul tanpa menghapus hasil yang sudah ada, sampai
# pengguna menekan "Mulai ulang".
STATE = {
    "status": "idle",          # idle | processing | done
    "total_file": 0,           # jumlah total file unik di folder uploads/ (kumulatif)
    "diproses": 0,             # jumlah file yang sudah dicoba diproses (kumulatif)
    "berhasil": 0,
    "gagal": 0,                # termasuk file gagal dibaca & file/duplikat yang dilewati
    "log": [],                 # list of {file, pesan}
    "hasil_rows": [],          # list of dict baris absensi harian (gabungan seluruh batch)
    "hasil_ringkasan": [],     # list of dict rekap statistik per pegawai (gabungan seluruh batch)
    "bidang_override": "",     # nama Bidang manual (opsional) untuk sheet rekap resmi
    "output_path": None,
    "mulai": None,
    "selesai": None,
    "processed_files": set(),        # nama file yang SUDAH pernah diproses (agar tidak diproses ulang)
    "file_hash_index": {},           # sha256(isi file) -> nama file pertama yang punya isi itu
    "content_signature_index": {},   # signature(NIP + rincian harian) -> nama file pertama
    "riwayat_batch": [],             # riwayat semua batch yang pernah selesai diproses di sesi
                                      # server ini (TIDAK ikut terhapus saat "Mulai ulang", supaya
                                      # batch lama tetap bisa diunduh meski sudah pindah ke batch baru)
}
LOCK = threading.Lock()


def _catat_ke_riwayat_jika_ada():
    """Simpan batch yang sedang berjalan ke riwayat (kalau memang sudah
    menghasilkan file Excel), dipanggil sebelum batch itu 'ditutup' -
    baik karena pengguna reset total maupun memilih 'buat batch baru
    terpisah'. Supaya file lama tetap bisa diunduh lewat riwayat."""
    if STATE["output_path"] and os.path.exists(STATE["output_path"]):
        STATE["riwayat_batch"].append({
            "nama_file": os.path.basename(STATE["output_path"]),
            "waktu": STATE["selesai"] or datetime.now().strftime("%H:%M:%S"),
            "jumlah_pegawai": len(STATE["hasil_ringkasan"]),
            "jumlah_baris": len(STATE["hasil_rows"]),
            "berhasil": STATE["berhasil"],
            "gagal": STATE["gagal"],
            "bidang": STATE.get("bidang_override") or "-",
        })


def reset_state():
    """Reset total: dipakai saat pengguna menekan 'Mulai ulang / unggah batch baru'
    ATAU saat memilih 'Buat batch baru terpisah' ketika menambah file susulan.
    Batch yang sedang berjalan (jika ada hasilnya) dicatat dulu ke riwayat
    sebelum dihapus, supaya tetap bisa diunduh belakangan."""
    with LOCK:
        _catat_ke_riwayat_jika_ada()
        STATE.update({
            "status": "idle",
            "total_file": 0,
            "diproses": 0,
            "berhasil": 0,
            "gagal": 0,
            "log": [],
            "hasil_rows": [],
            "hasil_ringkasan": [],
            "bidang_override": "",
            "output_path": None,
            "mulai": None,
            "selesai": None,
            "processed_files": set(),
            "file_hash_index": {},
            "content_signature_index": {},
        })
    # bersihkan folder uploads saja (file PDF sumber sudah tidak perlu lagi
    # setelah diproses). Folder output/ SENGAJA tidak dihapus supaya file
    # Excel dari batch-batch sebelumnya tetap bisa diunduh lewat riwayat.
    for f in os.listdir(UPLOAD_DIR):
        try:
            os.remove(os.path.join(UPLOAD_DIR, f))
        except OSError:
            pass


def _hash_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for potongan in iter(lambda: f.read(1024 * 1024), b""):
            h.update(potongan)
    return h.hexdigest()


def _signature_pegawai(nip, baris_pegawai):
    """Tanda tangan isi data harian satu pegawai (dipakai untuk mendeteksi
    file yang isinya sama meski nama filenya berbeda, mis. hasil ekspor
    ulang). Diambil dari NIP + kumpulan (tanggal, jam masuk, jam keluar,
    keterangan) yang diurutkan, supaya tidak terpengaruh urutan baris."""
    inti = sorted(
        (b.get("Tanggal", ""), b.get("Jam Masuk", ""), b.get("Jam Keluar", ""), b.get("Keterangan", ""))
        for b in baris_pegawai
    )
    teks = (nip or "") + "|" + "|".join(f"{a},{b},{c},{d}" for a, b, c, d in inti)
    return hashlib.sha256(teks.encode("utf-8")).hexdigest()


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """Terima file PDF (drag-drop / pilih file / pilih folder).
    Bersifat MENAMBAHKAN ke batch yang sedang berjalan - tidak menghapus
    file yang sebelumnya sudah diunggah/diproses, supaya pengguna bisa
    menambah file susulan tanpa perlu mulai ulang."""
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "pesan": "Tidak ada file yang diterima"}), 400

    disimpan = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            continue
        nama_aman = os.path.basename(f.filename)
        tujuan = os.path.join(UPLOAD_DIR, nama_aman)
        # hindari nama file bentrok (mis. file dengan nama sama diunggah lagi
        # di batch berikutnya) - disimpan dengan akhiran angka, dan akan
        # terdeteksi sebagai duplikat isi saat diproses jika memang sama persis
        i = 1
        base, ext = os.path.splitext(tujuan)
        while os.path.exists(tujuan):
            tujuan = f"{base}_{i}{ext}"
            i += 1
        f.save(tujuan)
        disimpan.append(os.path.basename(tujuan))

    with LOCK:
        total_sekarang = len([f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".pdf")])
        STATE["total_file"] = total_sekarang
        if STATE["status"] == "done":
            STATE["status"] = "idle"  # ada file baru menunggu diproses

    return jsonify({"ok": True, "jumlah": len(disimpan), "files": disimpan, "total_file": total_sekarang})


def _proses_job():
    with LOCK:
        STATE["status"] = "processing"
        if not STATE["mulai"]:
            STATE["mulai"] = datetime.now().strftime("%H:%M:%S")

    daftar_file = sorted(f for f in os.listdir(UPLOAD_DIR) if f.lower().endswith(".pdf"))

    for nama_file in daftar_file:
        with LOCK:
            if nama_file in STATE["processed_files"]:
                continue  # sudah diproses pada batch sebelumnya, lewati
            STATE["processed_files"].add(nama_file)

        path = os.path.join(UPLOAD_DIR, nama_file)

        # --- Lapis 1: deteksi file dengan ISI PERSIS SAMA (hash) ---
        try:
            file_hash = _hash_file(path)
        except OSError as e:
            with LOCK:
                STATE["diproses"] += 1
                STATE["gagal"] += 1
                STATE["log"].append({"file": nama_file, "pesan": f"Tidak bisa membaca file: {e}"})
            continue

        with LOCK:
            STATE["diproses"] += 1
            file_kembar = STATE["file_hash_index"].get(file_hash)
            if file_kembar:
                STATE["gagal"] += 1
                STATE["log"].append({
                    "file": nama_file,
                    "pesan": (
                        f"File duplikat - isi file ini persis sama dengan file yang sudah "
                        f"diunggah sebelumnya ('{file_kembar}'). Dilewati agar tidak dobel di rekap."
                    ),
                })
                continue
            STATE["file_hash_index"][file_hash] = nama_file

        # --- Ekstraksi ---
        rows, ringkasan, error = ekstrak_pdf(path, nama_file)

        with LOCK:
            if error:
                STATE["gagal"] += 1
                STATE["log"].append({"file": nama_file, "pesan": error})
                continue

            # --- Lapis 2: deteksi DATA yang sama (NIP + rincian harian sama),
            #     berguna kalau file yang sama diekspor ulang dengan nama beda ---
            ringkasan_baru = []
            rows_baru = []
            for r in ringkasan:
                nip = r.get("NIP", "-")
                baris_pegawai = [b for b in rows if b.get("NIP") == nip]
                sig = _signature_pegawai(nip, baris_pegawai)
                file_kembar_konten = STATE["content_signature_index"].get(sig)
                if file_kembar_konten:
                    STATE["log"].append({
                        "file": nama_file,
                        "pesan": (
                            f"Data duplikat - NIP {nip} ({r.get('Nama', '-')}) dengan rincian "
                            f"dan periode yang sama sudah pernah diproses dari file "
                            f"'{file_kembar_konten}'. Data pegawai ini dilewati agar tidak "
                            f"dobel di rekap."
                        ),
                    })
                    continue
                STATE["content_signature_index"][sig] = nama_file
                ringkasan_baru.append(r)
                rows_baru.extend(baris_pegawai)

            if ringkasan and not ringkasan_baru:
                # seluruh pegawai di file ini ternyata duplikat konten
                STATE["gagal"] += 1
                continue

            if ringkasan_baru:
                STATE["hasil_rows"].extend(rows_baru)
                STATE["hasil_ringkasan"].extend(ringkasan_baru)
            elif rows:
                # kasus jarang: ada baris harian tapi tidak ada ringkasan sama sekali
                STATE["hasil_rows"].extend(rows)

            STATE["berhasil"] += 1
        time.sleep(0.03)  # jeda kecil agar progress terlihat halus di UI

    # susun ulang file Excel dari SELURUH data terkumpul sejauh ini (semua batch)
    with LOCK:
        if STATE["hasil_rows"]:
            df = pd.DataFrame(STATE["hasil_rows"])
            kolom_urut = [
                "Nama", "NIP", "NRP", "Golongan", "Sub Unit Kerja", "Jabatan",
                "Tanggal", "Jadwal Masuk", "Jadwal Pulang", "Jam Masuk", "Jam Keluar",
                "Datang Awal", "Datang Telat", "Pulang Awal", "Pulang Telat",
                "Jumlah Jam Kerja", "Keterangan", "Sumber File",
            ]
            df = df[[c for c in kolom_urut if c in df.columns]]
            nama_output = f"rekap_absensi_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            path_output = os.path.join(OUTPUT_DIR, nama_output)

            # hapus file excel PERANTARA dari batch yang sama (kalau ini
            # bukan file pertama untuk batch ini, mis. akibat "Proses File
            # Baru" susulan) - supaya tidak menumpuk sampah; file yang sudah
            # "ditutup" ke riwayat via _catat_ke_riwayat_jika_ada() TIDAK
            # akan kena karena sudah tidak lagi jadi STATE["output_path"] saat itu
            if STATE["output_path"] and os.path.exists(STATE["output_path"]):
                try:
                    os.remove(STATE["output_path"])
                except OSError:
                    pass

            with pd.ExcelWriter(path_output, engine="openpyxl") as writer:
                df.to_excel(writer, index=False, sheet_name="Rekap Absensi Harian")
                ws = writer.sheets["Rekap Absensi Harian"]
                for i, col in enumerate(df.columns, start=1):
                    max_len = max([len(str(col))] + [len(str(v)) for v in df[col].astype(str).tolist()[:2000]])
                    huruf = chr(64 + i) if i <= 26 else "A" + chr(64 + i - 26)
                    ws.column_dimensions[huruf].width = min(max_len + 4, 45)

                if STATE["hasil_ringkasan"]:
                    df_ringkasan = pd.DataFrame(STATE["hasil_ringkasan"])
                    kolom_tampil = [c for c in df_ringkasan.columns if not c.startswith("_")]
                    df_ringkasan[kolom_tampil].to_excel(writer, index=False, sheet_name="Ringkasan Kehadiran")
                    ws2 = writer.sheets["Ringkasan Kehadiran"]
                    for i, col in enumerate(kolom_tampil, start=1):
                        max_len = max([len(str(col))] + [len(str(v)) for v in df_ringkasan[col].astype(str).tolist()[:2000]])
                        huruf = chr(64 + i) if i <= 26 else "A" + chr(64 + i - 26)
                        ws2.column_dimensions[huruf].width = min(max_len + 4, 45)

                if STATE["log"]:
                    df_log = pd.DataFrame(STATE["log"])
                    df_log.to_excel(writer, index=False, sheet_name="Log Kesalahan")

                # sheet tambahan: format resmi instansi
                if STATE["hasil_ringkasan"]:
                    semua_tanggal = [r.get("Tanggal") for r in STATE["hasil_rows"]]
                    tulis_sheet_rekap_resmi(
                        writer.book, STATE["hasil_ringkasan"], semua_tanggal,
                        nama_bidang=STATE.get("bidang_override", ""),
                    )

            STATE["output_path"] = path_output

        STATE["status"] = "done"
        STATE["selesai"] = datetime.now().strftime("%H:%M:%S")


@app.route("/api/process", methods=["POST"])
def process():
    with LOCK:
        if STATE["status"] == "processing":
            return jsonify({"ok": False, "pesan": "Proses sedang berjalan"}), 409
        belum_diproses = [
            f for f in os.listdir(UPLOAD_DIR)
            if f.lower().endswith(".pdf") and f not in STATE["processed_files"]
        ]
        if not belum_diproses:
            return jsonify({"ok": False, "pesan": "Tidak ada file baru untuk diproses"}), 400
        data = request.get_json(silent=True) or {}
        bidang_baru = (data.get("bidang_override") or "").strip()
        if bidang_baru:
            STATE["bidang_override"] = bidang_baru
    t = threading.Thread(target=_proses_job, daemon=True)
    t.start()
    return jsonify({"ok": True, "jumlah_baru": len(belum_diproses)})


@app.route("/api/status")
def status():
    with LOCK:
        preview = STATE["hasil_rows"][-8:] if STATE["hasil_rows"] else []
        return jsonify({
            "status": STATE["status"],
            "total_file": STATE["total_file"],
            "diproses": STATE["diproses"],
            "berhasil": STATE["berhasil"],
            "gagal": STATE["gagal"],
            "total_baris": len(STATE["hasil_rows"]),
            "log": STATE["log"][-30:],
            "preview": preview,
            "mulai": STATE["mulai"],
            "selesai": STATE["selesai"],
            "siap_unduh": STATE["output_path"] is not None,
        })


@app.route("/api/download")
def download():
    with LOCK:
        path = STATE["output_path"]
    if not path or not os.path.exists(path):
        return jsonify({"ok": False, "pesan": "Belum ada file hasil untuk diunduh"}), 404
    return send_file(path, as_attachment=True, download_name=os.path.basename(path))


@app.route("/api/riwayat")
def riwayat():
    with LOCK:
        # terbaru duluan
        return jsonify({"riwayat": list(reversed(STATE["riwayat_batch"]))})


@app.route("/api/download-riwayat/<nama_file>")
def download_riwayat(nama_file):
    nama_aman = os.path.basename(nama_file)  # cegah path traversal
    path = os.path.join(OUTPUT_DIR, nama_aman)
    if not os.path.exists(path):
        return jsonify({"ok": False, "pesan": "File riwayat ini sudah tidak ada di server"}), 404
    return send_file(path, as_attachment=True, download_name=nama_aman)


@app.route("/api/reset", methods=["POST"])
def reset():
    reset_state()
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("=" * 60)
    print(" Sistem Rekapitulasi Absensi - Daskrimti Kejati Jateng")
    print(" Buka browser: http://127.0.0.1:5000")
    print("=" * 60)
    app.run(debug=True, port=5000)
