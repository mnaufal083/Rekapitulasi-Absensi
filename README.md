# Sistem Rekapitulasi Absensi Otomatis
### Bidang Daskrimti — Kejaksaan Tinggi Jawa Tengah (Prototipe Web Lokal)

Aplikasi ini membaca banyak file PDF absensi pegawai sekaligus, mengekstraksi
datanya secara otomatis, dan menggabungkannya menjadi **satu file rekap
Excel** — menggantikan proses pengecekan manual satu per satu.

Versi ini **berbasis web tapi berjalan 100% lokal di komputer sendiri**
(bukan di-hosting online), sehingga data pegawai tidak pernah keluar dari
perangkat kalian.

---

## 1. Yang perlu disiapkan (sekali saja)

1. **Python 3.10 ke atas** — cek dengan `python --version` di terminal.
   Kalau belum ada, unduh di [python.org/downloads](https://www.python.org/downloads/)
   (saat instalasi di Windows, centang **"Add Python to PATH"**).
2. **Visual Studio Code** — [code.visualstudio.com](https://code.visualstudio.com/)
3. Ekstensi **Python** dari Microsoft di VS Code (buka tab Extensions, cari "Python", Install).

---

## 2. Membuka proyek di VS Code

1. Ekstrak (unzip) folder proyek ini di lokasi mana saja, misalnya di Desktop.
2. Buka VS Code → `File` → `Open Folder...` → pilih folder `absensi-web`.
3. Buka terminal bawaan VS Code: menu `Terminal` → `New Terminal`
   (atau tekan `` Ctrl+` ``).

---

## 3. Menyiapkan environment Python (hanya sekali di awal)

Di terminal VS Code, jalankan baris berikut satu per satu:

```bash
# 1. Buat virtual environment (folder khusus paket python untuk proyek ini)
python -m venv venv

# 2. Aktifkan virtual environment
# Windows (PowerShell):
venv\Scripts\Activate.ps1
# Windows (Command Prompt):
venv\Scripts\activate.bat
# macOS / Linux:
source venv/bin/activate

# 3. Install semua paket yang dibutuhkan
pip install -r requirements.txt
```

Jika berhasil, di depan baris terminal akan muncul tanda `(venv)`.
Setelah ini, di VS Code bagian kanan bawah pastikan Python Interpreter yang
dipakai adalah `./venv/...` (klik untuk memilih jika belum sesuai).

---

## 4. (Opsional) Membuat contoh data untuk uji coba

Karena kalian belum tentu langsung punya 380 file PDF asli untuk mencoba,
proyek ini menyediakan skrip pembuat contoh data:

```bash
python generate_sample_pdfs.py
```

Ini akan membuat 8 file PDF contoh di folder `sample_pdfs/` yang bisa
langsung dipakai untuk mencoba aplikasi dari awal sampai akhir.

---

## 5. Menjalankan aplikasi

```bash
python app.py
```

Kalau berhasil, di terminal akan muncul pesan seperti:

```
 Sistem Rekapitulasi Absensi - Daskrimti Kejati Jateng
 Buka browser: http://127.0.0.1:5000
```

Buka browser (Chrome/Edge disarankan), lalu akses:

```
http://127.0.0.1:5000
```

Aplikasi akan tampil. Untuk **menghentikan** server, kembali ke terminal
VS Code dan tekan `Ctrl+C`.

---

## 6. Cara memakai aplikasinya

1. **Unggah file** — tarik & letakkan (drag & drop) file PDF ke kotak unggah,
   atau klik **"Pilih File PDF"** (pilih banyak file sekaligus), atau klik
   **"Pilih Folder"** untuk langsung memilih seluruh folder berisi PDF.
2. Klik **"Proses Semua File"**. Progress bar akan menunjukkan file
   ke berapa yang sedang diproses, dan tabel pratinjau akan terisi
   secara langsung (live).
3. Kartu di bagian atas menunjukkan ringkasan: total file, jumlah berhasil,
   jumlah gagal/perlu dicek, dan total baris data yang berhasil dikumpulkan.
4. Jika ada file yang gagal dibaca, akan muncul di panel **"Log Berkas
   Bermasalah"** lengkap dengan alasannya — supaya kalian tidak perlu
   mengecek ulang semua file, cukup yang bermasalah saja.
5. Setelah selesai, klik **"Unduh Rekap Excel (.xlsx)"**. File akan berisi
   dua sheet: `Rekap Absensi` (data gabungan) dan `Log Kesalahan`
   (jika ada file yang gagal diproses).
6. Klik **"Mulai ulang / unggah batch baru"** untuk memproses kelompok
   file lain.

---

## 7. Memasang logo resmi Kejaksaan

Header aplikasi sudah disiapkan menampilkan logo secara statis (tidak
berputar/bergerak). Untuk memasangnya:

1. Siapkan file logo resmi (format **PNG dengan latar belakang transparan**
   akan tampil paling rapi di atas warna hijau header). Ukuran persegi,
   minimal 200x200 px, cukup ideal.
2. Beri nama file tersebut persis: **`logo-kejaksaan.png`**
3. Salin/taruh file itu ke folder:
   ```
   absensi-web/static/img/logo-kejaksaan.png
   ```
4. Simpan, lalu refresh browser (`http://127.0.0.1:5000`) — logo akan
   otomatis tampil menggantikan tempat kosong tersebut, ukurannya sudah
   otomatis menyesuaikan (72x72 px) dan tidak ada animasi apa pun.

Kalau nanti ingin ukuran tampilnya diperbesar/diperkecil, bisa disesuaikan
lewat `static/css/style.css`, cari bagian:
```css
.seal{
  width: 72px;
  height: 72px;
}
```
tinggal ubah angka `72px` sesuai kebutuhan.

---

## 8. Status Kalibrasi — SUDAH SESUAI FORMAT ASLI ✅

Modul `extractor.py` sudah dikalibrasi langsung berdasarkan contoh PDF
**asli** "LAPORAN KEHADIRAN PEGAWAI" dari Kejaksaan Tinggi Jawa Tengah,
dan sudah diuji berhasil membaca dengan akurat, termasuk:

- Identitas pegawai: Nama, NIP, NRP, Golongan, Sub Unit Kerja, Jabatan
- Data harian: Tanggal, Jadwal Masuk/Pulang, Jam Masuk/Keluar aktual,
  Datang Awal/Telat, Pulang Awal/Telat, Jumlah Jam Kerja, Keterangan (WFO/dsb)
- Hari libur/akhir pekan otomatis diberi label **"Libur"**
- **Ringkasan statistik per pegawai** (Terlambat, Alpha, Sakit, Izin,
  Dinas Luar, Cuti, Total Hari Kerja, dst) — diambil otomatis dari blok
  rekap di bagian akhir laporan, dan disusun sebagai **sheet Excel
  terpisah** ("Ringkasan Kehadiran"), selain sheet data harian
  ("Rekap Absensi Harian").

Artinya file Excel hasil rekap sekarang berisi **dua sheet**:
1. `Rekap Absensi Harian` — satu baris per tanggal per pegawai
2. `Ringkasan Kehadiran` — satu baris per pegawai, rekap total statistiknya

Jika suatu saat ternyata ada pegawai/unit dengan format tabel yang sedikit
berbeda (misal ada kolom tambahan), akan otomatis masuk ke Log Kesalahan
dengan pesan yang jelas, tanpa menghentikan proses file lainnya — tinggal
dikirimkan contohnya untuk disesuaikan lebih lanjut.

---

## 9. Sheet Rekap Resmi (Format Persis Dokumen Instansi)

Selain sheet `Rekap Absensi Harian` dan `Ringkasan Kehadiran`, file Excel
hasil menyertakan **sheet tambahan** dengan format PERSIS seperti dokumen
resmi instansi (contoh acuan: "Rekapitulasi Absensi Digital Kejaksaan
Tinggi Jawa Tengah").

Di halaman utama aplikasi ada kolom **"Nama Bidang untuk batch ini
(opsional)"**. Ini mengikuti cara kerja kantor yang biasanya memproses
absensi per Bidang sekaligus (satu batch unggah = satu Bidang):

- **Kalau diisi** (mis. `PIDMIL`): seluruh pegawai di batch itu akan
  diberi nilai Bidang tersebut di kolom "Bidang", dan sheet-nya otomatis
  diberi nama sesuai Bidang itu (mis. sheet **"Pidmil"**) - persis seperti
  kebiasaan satu sheet per Bidang di dokumen asli.
- **Kalau dikosongkan**: kolom "Bidang" dibiarkan kosong untuk semua
  pegawai, dan sheet-nya diberi nama umum **"Rekapitulasi Absensi"**.
  Dipakai kalau file yang diunggah memang berasal dari beberapa Bidang
  berbeda sekaligus dalam satu batch.

Sheet ini juga mempertahankan semua penyesuaian sebelumnya:

- Kolom **"Cuti" menampilkan rincian jenis cuti** (mis. `CUTI ALASAN
  PENTING : 5 Hari, CUTI BESAR : 3 Hari, CUTI PENANGGUHAN TAHUN LALU : 3
  Hari`), diambil otomatis dari baris statistik tambahan di PDF sumber -
  sistem mengenali pola apa pun berbentuk `"LABEL : angka Hari"`, jadi
  jenis cuti apa pun otomatis tertangkap tanpa perlu didaftarkan manual.
- Judul, periode, jumlah hari kerja, header tabel, font, lebar kolom,
  garis tabel, dan aturan "sel dikosongkan jika nilai 0" disamakan
  dengan dokumen acuan.

**Catatan:** karena contoh PDF yang saya terima kebetulan tidak punya
data cuti (Total Cuti = 0 Hari), fitur rincian cuti sudah diuji dengan
data simulasi dan terbukti bekerja sesuai pola yang diminta, tapi belum
diuji dengan PDF asli yang benar-benar memiliki rincian cuti. Kalau nanti
ditemukan pola yang sedikit berbeda dari dugaan, kabari saya dengan
contoh PDF-nya.

---

## 10. Unggah Bertahap & Deteksi Duplikat

Dua penyempurnaan tambahan supaya lebih tahan-banting dipakai untuk
volume besar (mis. 380 file bertahap dari beberapa pembina/waktu):

**Unggah bertahap (tidak perlu mulai ulang).** Kalau ada file susulan
yang ketinggalan, tinggal pilih/tarik file baru itu lagi kapan pun -
baik sebelum maupun SETELAH batch sebelumnya selesai diproses. Klik
"Proses File Baru" untuk memproses hanya file yang baru ditambahkan;
hasil dari batch-batch sebelumnya tetap tersimpan dan digabung otomatis
ke rekap yang sama. Tombol "Mulai ulang / unggah batch baru" tetap ada
kalau memang ingin benar-benar mulai dari nol.

**Deteksi file duplikat.** Kalau file yang sama tidak sengaja terunggah
lagi, sistem otomatis mendeteksinya lewat dua cara sekaligus, supaya
tidak dobel di rekap:
1. **Isi file persis sama** (dibandingkan lewat hash isi file) - menangkap
   kasus file yang sama betul-betul diunggah dua kali, walau namanya
   diganti.
2. **Data sama walau file beda** (dibandingkan lewat NIP + rincian
   tanggal/jam/keterangan harian) - menangkap kasus file diekspor ulang
   dari sistem sumber (nama file & metadata beda, tapi isinya sama).

File yang terdeteksi duplikat otomatis masuk ke **"Log Berkas
Bermasalah"** dengan keterangan file mana yang jadi acuan duplikatnya,
dan tidak ikut dihitung dua kali di rekap Excel maupun sheet resmi.
Sheet "Log Kesalahan" di file Excel hasil juga mencatat hal yang sama.

Untuk mencoba fitur ini tanpa menunggu kasus nyata, `generate_sample_pdfs.py`
sudah menyertakan satu file contoh duplikat bernama
`absensi_001_BUDI_SANTOSO_EKSPOR_ULANG.pdf` - coba unggah file itu
bersamaan dengan `absensi_001_BUDI_SANTOSO.pdf` untuk melihat cara
kerjanya langsung.

---

## 11. PENTING — Jika nanti ditemukan format yang sedikit berbeda

Karena contoh format PDF absensi asli dari kantor belum tersedia saat
proyek ini dibuat, logika pembacaan PDF (`extractor.py`) ditulis secara
umum berdasarkan pola absensi yang lazim (blok Nama/NIP + tabel harian).

**Sebelum dipakai untuk 380 file asli**, lakukan langkah kalibrasi berikut:

1. Ambil 2-3 contoh PDF absensi **asli** dari kantor.
2. Jalankan perintah berikut untuk melihat bagaimana teksnya terbaca:
   ```bash
   python -c "import pdfplumber; print(pdfplumber.open('contoh_asli.pdf').pages[0].extract_text())"
   ```
3. Bandingkan hasilnya dengan pola regex di `extractor.py` — cari bagian
   berkomentar `# KALIBRASI 1` dan `# KALIBRASI 2`, lalu sesuaikan kata
   kunci/label yang dicari (misalnya jika PDF asli menulis "Nomor Induk
   Pegawai" bukan "NIP", tambahkan pola barunya di situ).
4. Uji ulang dengan file asli tersebut, cek di tabel pratinjau apakah
   Nama/NIP/Tanggal/Jam sudah terbaca dengan benar.
5. Jika sudah sesuai, baru jalankan untuk seluruh 380 file.

Kalau kalian mau, tahap kalibrasi ini juga bisa dibantu lebih lanjut —
tinggal kirimkan 1-2 contoh PDF (boleh data disamarkan/dummy) untuk
disesuaikan polanya.

---

## 12. Struktur proyek

```
absensi-web/
├── app.py                    # Server web (Flask) - alur upload, proses, unduh
├── extractor.py               # Logika pembaca & pengekstrak data PDF (bagian yang dikalibrasi)
├── generate_sample_pdfs.py    # Skrip opsional pembuat contoh PDF untuk uji coba
├── requirements.txt            # Daftar paket Python yang dibutuhkan
├── templates/
│   └── index.html              # Tampilan halaman utama
├── static/
│   ├── css/style.css           # Gaya visual aplikasi
│   └── js/app.js               # Interaksi tombol, upload, progress, dsb.
├── sample_pdfs/                # Tempat contoh PDF hasil generate_sample_pdfs.py
├── uploads/                    # Tempat sementara file yang diunggah (otomatis)
└── output/                     # Tempat file Excel hasil rekap tersimpan (otomatis)
```

---

## 13. Rencana pengembangan lanjutan (setelah versi web lokal ini stabil)

Sesuai diskusi sebelumnya, setelah versi web ini terbukti bekerja dengan
baik terhadap data asli, langkah selanjutnya sesuai proposal adalah
membungkusnya menjadi **aplikasi desktop mandiri** (file yang bisa
langsung dijalankan tanpa perlu membuka terminal/VS Code), menggunakan
`pyinstaller`, supaya staf non-teknis di bidang Daskrimti bisa memakainya
dengan sekali klik setiap bulan.

---

## 14. Batas ukuran total unggahan

Secara default aplikasi mengizinkan total unggahan sekaligus sampai
**2 GB** (cukup luas untuk ~380 file PDF, bahkan jika sebagian besar
ukurannya). Kalau suatu saat ternyata masih kurang atau ingin diperkecil,
ubah angka ini di `app.py`:

```python
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024 * 1024  # ganti angkanya di sini
```

Jika total unggahan melebihi batas, aplikasi akan menampilkan pesan error
yang jelas di layar (bukan halaman error mentah), dan kalian bisa coba
unggah dalam beberapa kelompok/batch yang lebih kecil sebagai alternatif
(misalnya 100 file dulu, unduh hasil rekapnya, lalu 100 file berikutnya,
dan digabung manual di Excel di akhir — atau beri tahu saya kalau mau
dibuatkan fitur "gabung otomatis antar batch").

---

Kalau ada error yang muncul di terminal saat menjalankan, silakan salin
pesan errornya — akan lebih mudah dibantu menelusuri penyebabnya dengan
melihat pesan tersebut.
