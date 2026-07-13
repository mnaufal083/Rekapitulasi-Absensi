# -*- coding: utf-8 -*-
"""
extractor.py
------------
Modul pembaca PDF "LAPORAN KEHADIRAN PEGAWAI" - Kejaksaan Tinggi Jawa Tengah.

Dikalibrasi berdasarkan contoh PDF asli (format sistem absensi instansi):
tabel dengan 16 kolom tetap (NO, NAMA PEGAWAI, NIP, NRP, GOL, TANGGAL,
JAM KERJA MASUK, JAM KERJA PULANG, JAM MASUK, JAM KELUAR, DATANG AWAL,
DATANG TELAT, PULANG AWAL, PULANG TELAT, JML JAM KERJA, KETERANGAN),
diikuti blok ringkasan statistik kehadiran (Terlambat, Alpha, Sakit, dst)
di baris/halaman terakhir setiap pegawai.

Fungsi utama: ekstrak_pdf(path_pdf, nama_file)
Mengembalikan: (rows, ringkasan, error)
  rows       -> list dict, satu baris per tanggal kehadiran
  ringkasan  -> list dict, satu baris per pegawai berisi rekap statistik
  error      -> None jika sukses, atau string peringatan/alasan gagal
"""

import re
import pdfplumber
from datetime import datetime

TANGGAL_REGEX = re.compile(r"^\d{1,2}-[A-Za-z]{3}-\d{4}$")
RINGKASAN_REGEX = re.compile(r"([A-Z][A-Z /]*?)\s*:\s*(\d+)\s*Hari")

# Indeks kolom tetap sesuai header tabel PDF asli (0-based)
COL_NO = 0
COL_NAMA = 1
COL_NIP = 2
COL_NRP = 3
COL_GOL = 4
COL_TANGGAL = 5
COL_JADWAL_MASUK = 6
COL_JADWAL_PULANG = 7
COL_JAM_MASUK = 8
COL_JAM_KELUAR = 9
COL_DATANG_AWAL = 10
COL_DATANG_TELAT = 11
COL_PULANG_AWAL = 12
COL_PULANG_TELAT = 13
COL_JML_JAM = 14
COL_KETERANGAN = 15
JUMLAH_KOLOM_DIHARAPKAN = 16


def _bersih(v):
    if v is None:
        return ""
    return str(v).replace("\n", " ").strip()


def _format_tanggal(v):
    """20-May-2026 -> 20/05/2026 (lebih mudah dipakai di Excel/filter)."""
    v = _bersih(v)
    try:
        return datetime.strptime(v, "%d-%b-%Y").strftime("%d/%m/%Y")
    except ValueError:
        return v  # biarkan format asli jika gagal parse


def _adalah_header(row):
    c0, c1 = _bersih(row[0]).upper(), _bersih(row[1]).upper() if len(row) > 1 else ""
    return c0.startswith("NO.") and "NAMA" in c1


def _adalah_subheader_jam(row):
    # baris kedua header: [None,...,'MASUK','PULANG',None...]
    joined = " ".join(_bersih(x) for x in row).upper()
    return joined.strip() in ("MASUK PULANG",)


def _adalah_baris_subunit(row):
    return _bersih(row[0]).upper().startswith("SUB UNIT KERJA")


def _adalah_baris_jabatan(row):
    return _bersih(row[0]).upper().startswith("JABATAN")


def _adalah_baris_ringkasan(row):
    return "TERLAMBAT" in _bersih(row[0]).upper() and "HARI" in _bersih(row[0]).upper()


def _parse_ringkasan(teks, nama, nip, nrp, gol, sumber_file):
    hasil = {label.strip().title(): int(jumlah) for label, jumlah in RINGKASAN_REGEX.findall(teks)}
    return {
        "Nama": nama or "-",
        "NIP": nip or "-",
        "NRP": nrp or "-",
        "Golongan": gol or "-",
        "Terlambat (Hari)": hasil.get("Terlambat", ""),
        "Pulang Cepat (Hari)": hasil.get("Pulang Cepat", ""),
        "Tidak Absen Datang (Hari)": hasil.get("Tidak Absen Datang", ""),
        "Tidak Absen Pulang (Hari)": hasil.get("Tidak Absen Pulang", ""),
        "Izin (Hari)": hasil.get("Izin", ""),
        "Alpha (Hari)": hasil.get("Alpha", ""),
        "Sakit (Hari)": hasil.get("Sakit", ""),
        "Dinas Luar (Hari)": hasil.get("Dinas Luar", ""),
        "Lepas Piket (Hari)": hasil.get("Lepas Piket", ""),
        "Tugas Belajar (Hari)": hasil.get("Tugas Belajar", ""),
        "Total Cuti (Hari)": hasil.get("Total Cuti", ""),
        "Total Hari Kerja": hasil.get("Total Hari Kerja", ""),
        "Sumber File": sumber_file,
    }


def ekstrak_pdf(path_pdf, nama_file):
    rows = []
    ringkasan_list = []
    ditemukan_tabel = False

    # state yang di-"bawa turun" karena pada baris ke-2 dst NO/Nama/NIP/dst dikosongkan
    cur = {"no": "", "nama": "", "nip": "", "nrp": "", "gol": "", "subunit": "", "jabatan": ""}

    try:
        with pdfplumber.open(path_pdf) as pdf:
            if len(pdf.pages) == 0:
                return [], [], "File PDF kosong / tidak memiliki halaman"

            for page in pdf.pages:
                tables = page.extract_tables()
                for table in tables:
                    for row in table:
                        if len(row) < JUMLAH_KOLOM_DIHARAPKAN:
                            continue
                        if _adalah_header(row) or _adalah_subheader_jam(row):
                            ditemukan_tabel = True
                            continue
                        if _adalah_baris_subunit(row):
                            cur["subunit"] = _bersih(row[0])
                            continue
                        if _adalah_baris_jabatan(row):
                            cur["jabatan"] = _bersih(row[0])
                            continue
                        if _adalah_baris_ringkasan(row):
                            ringkasan_list.append(_parse_ringkasan(
                                _bersih(row[0]), cur["nama"], cur["nip"], cur["nrp"], cur["gol"], nama_file
                            ))
                            continue

                        tanggal_raw = _bersih(row[COL_TANGGAL])
                        if not TANGGAL_REGEX.match(tanggal_raw):
                            continue  # baris tidak dikenali, lewati dengan aman

                        # update state kalau kolom identitas terisi (baris pertama pegawai)
                        if _bersih(row[COL_NAMA]):
                            cur["no"] = _bersih(row[COL_NO])
                            cur["nama"] = _bersih(row[COL_NAMA])
                            cur["nip"] = _bersih(row[COL_NIP])
                            cur["nrp"] = _bersih(row[COL_NRP])
                            cur["gol"] = _bersih(row[COL_GOL])

                        keterangan = _bersih(row[COL_KETERANGAN])
                        jadwal_masuk = _bersih(row[COL_JADWAL_MASUK])
                        jadwal_pulang = _bersih(row[COL_JADWAL_PULANG])
                        if not keterangan and jadwal_masuk == "00:00" and jadwal_pulang == "00:00":
                            keterangan = "Libur"

                        rows.append({
                            "Nama": cur["nama"] or "-",
                            "NIP": cur["nip"] or "-",
                            "NRP": cur["nrp"] or "-",
                            "Golongan": cur["gol"] or "-",
                            "Sub Unit Kerja": cur["subunit"].replace("SUB UNIT KERJA", "").strip(" :"),
                            "Jabatan": cur["jabatan"].replace("JABATAN", "").strip(" :"),
                            "Tanggal": _format_tanggal(tanggal_raw),
                            "Jadwal Masuk": jadwal_masuk,
                            "Jadwal Pulang": jadwal_pulang,
                            "Jam Masuk": _bersih(row[COL_JAM_MASUK]),
                            "Jam Keluar": _bersih(row[COL_JAM_KELUAR]),
                            "Datang Awal": _bersih(row[COL_DATANG_AWAL]),
                            "Datang Telat": _bersih(row[COL_DATANG_TELAT]),
                            "Pulang Awal": _bersih(row[COL_PULANG_AWAL]),
                            "Pulang Telat": _bersih(row[COL_PULANG_TELAT]),
                            "Jumlah Jam Kerja": _bersih(row[COL_JML_JAM]),
                            "Keterangan": keterangan,
                            "Sumber File": nama_file,
                        })

            if not ditemukan_tabel:
                return [], [], "Struktur tabel tidak dikenali (header 'NO./NAMA PEGAWAI' tidak ditemukan) - kemungkinan format PDF berbeda"

            if not rows:
                return [], [], "Tabel ditemukan tetapi tidak ada baris tanggal yang cocok"

            return rows, ringkasan_list, None

    except Exception as e:
        return [], [], f"Gagal membuka/membaca PDF: {e}"
