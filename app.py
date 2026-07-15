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
import threading
import time
import uuid
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

# Status proses disimpan di memori (cukup untuk pemakaian lokal 1 pengguna)
STATE = {
    "status": "idle",          # idle | uploading | processing | done | error
    "total_file": 0,
    "diproses": 0,
    "berhasil": 0,
    "gagal": 0,
    "log": [],                 # list of {file, pesan}
    "hasil_rows": [],          # list of dict baris absensi harian
    "hasil_ringkasan": [],     # list of dict rekap statistik per pegawai
    "bidang_override": "",     # nama Bidang manual (opsional) untuk sheet rekap resmi
    "output_path": None,
    "mulai": None,
    "selesai": None,
}
LOCK = threading.Lock()


def reset_state():
    with LOCK:
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
        })


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/upload", methods=["POST"])
def upload():
    """Terima banyak file PDF sekaligus (drag-drop atau pilih folder)."""
    reset_state()
    files = request.files.getlist("files")
    if not files:
        return jsonify({"ok": False, "pesan": "Tidak ada file yang diterima"}), 400

    # bersihkan folder uploads sebelumnya
    for f in os.listdir(UPLOAD_DIR):
        try:
            os.remove(os.path.join(UPLOAD_DIR, f))
        except OSError:
            pass

    disimpan = []
    for f in files:
        if not f.filename.lower().endswith(".pdf"):
            continue
        nama_aman = os.path.basename(f.filename)
        tujuan = os.path.join(UPLOAD_DIR, nama_aman)
        # hindari nama file bentrok
        i = 1
        base, ext = os.path.splitext(tujuan)
        while os.path.exists(tujuan):
            tujuan = f"{base}_{i}{ext}"
            i += 1
        f.save(tujuan)
        disimpan.append(os.path.basename(tujuan))

    with LOCK:
        STATE["total_file"] = len(disimpan)

    return jsonify({"ok": True, "jumlah": len(disimpan), "files": disimpan})


def _proses_job():
    with LOCK:
        STATE["status"] = "processing"
        STATE["mulai"] = datetime.now().strftime("%H:%M:%S")

    daftar_file = sorted(os.listdir(UPLOAD_DIR))
    for nama_file in daftar_file:
        if not nama_file.lower().endswith(".pdf"):
            continue
        path = os.path.join(UPLOAD_DIR, nama_file)
        rows, ringkasan, error = ekstrak_pdf(path, nama_file)

        with LOCK:
            STATE["diproses"] += 1
            if rows:
                STATE["hasil_rows"].extend(rows)
            if ringkasan:
                STATE["hasil_ringkasan"].extend(ringkasan)
            if error:
                STATE["gagal"] += 1
                STATE["log"].append({"file": nama_file, "pesan": error})
            else:
                STATE["berhasil"] += 1
        time.sleep(0.03)  # jeda kecil agar progress terlihat halus di UI

    # susun file Excel akhir
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
        data = request.get_json(silent=True) or {}
        STATE["bidang_override"] = (data.get("bidang_override") or "").strip()
    t = threading.Thread(target=_proses_job, daemon=True)
    t.start()
    return jsonify({"ok": True})


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
            "log": STATE["log"][-20:],
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
