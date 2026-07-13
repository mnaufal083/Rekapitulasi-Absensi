# -*- coding: utf-8 -*-
"""
generate_sample_pdfs.py
------------------------
Skrip BANTUAN (opsional) untuk membuat contoh file PDF absensi
sehingga kalian bisa langsung mencoba alur kerja aplikasi web
sebelum memakai 380 file data asli.

Cara pakai:
    python generate_sample_pdfs.py

Hasil akan tersimpan di folder sample_pdfs/, lalu bisa langsung
di-drag & drop ke aplikasi web (folder tersebut) untuk uji coba.

Catatan: skrip ini HANYA untuk simulasi/latihan. Format tabel yang
dibuat di sini adalah asumsi umum -- setelah kalian punya contoh PDF
absensi ASLI dari kantor, sesuaikan pola pembacaan di extractor.py
(lihat komentar "KALIBRASI" di file tersebut).
"""

import os
import random
from datetime import date, timedelta

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "sample_pdfs")
os.makedirs(OUT_DIR, exist_ok=True)

NAMA_CONTOH = [
    ("Budi Santoso", "196801011990031001"),
    ("Siti Aminah", "197203152001122002"),
    ("Agus Wibowo", "198005202005011003"),
    ("Dewi Lestari", "199001102015022004"),
    ("Hendra Kurniawan", "198511302010011005"),
    ("Rina Marlina", "199206252016022006"),
    ("Fajar Ramadhan", "199512182019011007"),
    ("Yuni Astuti", "198709102012022008"),
]

KETERANGAN_OPSI = ["Hadir", "Hadir", "Hadir", "Hadir", "Izin", "Sakit", "Dinas Luar", "Cuti"]
HARI_MAP = ["Senin", "Selasa", "Rabu", "Kamis", "Jumat"]


def buat_pdf_pegawai(nama, nip, bulan_awal, jumlah_hari, path_output):
    doc = SimpleDocTemplate(path_output, pagesize=A4,
                             topMargin=1.5 * cm, bottomMargin=1.5 * cm,
                             leftMargin=1.5 * cm, rightMargin=1.5 * cm)
    styles = getSampleStyleSheet()
    elemen = []

    elemen.append(Paragraph("LAPORAN ABSENSI PEGAWAI", styles["Title"]))
    elemen.append(Paragraph("Kejaksaan Tinggi Jawa Tengah &mdash; Bidang Daskrimti", styles["Normal"]))
    elemen.append(Spacer(1, 10))
    elemen.append(Paragraph(f"Nama : {nama}", styles["Normal"]))
    elemen.append(Paragraph(f"NIP : {nip}", styles["Normal"]))
    elemen.append(Paragraph(f"Periode : {bulan_awal.strftime('%B %Y')}", styles["Normal"]))
    elemen.append(Spacer(1, 14))

    data = [["Tanggal", "Hari", "Jam Masuk", "Jam Keluar", "Keterangan"]]
    for i in range(jumlah_hari):
        tgl = bulan_awal + timedelta(days=i)
        if tgl.weekday() >= 5:  # skip akhir pekan
            continue
        ket = random.choice(KETERANGAN_OPSI)
        if ket == "Hadir":
            jam_masuk = f"{random.randint(6,8):02d}:{random.randint(0,59):02d}"
            jam_keluar = f"{random.randint(15,17):02d}:{random.randint(0,59):02d}"
        else:
            jam_masuk, jam_keluar = "-", "-"
        data.append([tgl.strftime("%d/%m/%Y"), HARI_MAP[tgl.weekday()], jam_masuk, jam_keluar, ket])

    tabel = Table(data, colWidths=[2.6 * cm, 2.4 * cm, 2.8 * cm, 2.8 * cm, 3.4 * cm])
    tabel.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1F4E37")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CCCCCC")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F2F2F2")]),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
    ]))
    elemen.append(tabel)

    doc.build(elemen)


def main():
    bulan_awal = date(2026, 6, 1)
    for i, (nama, nip) in enumerate(NAMA_CONTOH, start=1):
        nama_file = f"absensi_{i:03d}_{nama.replace(' ', '_')}.pdf"
        path_output = os.path.join(OUT_DIR, nama_file)
        buat_pdf_pegawai(nama, nip, bulan_awal, 30, path_output)
        print(f"  dibuat: {nama_file}")
    print(f"\nSelesai. {len(NAMA_CONTOH)} contoh PDF tersimpan di: {OUT_DIR}")
    print("Silakan drag & drop folder 'sample_pdfs' ini ke aplikasi web untuk uji coba.")


if __name__ == "__main__":
    main()
