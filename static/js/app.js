(() => {
  const dropZone = document.getElementById("dropZone");
  const fileInput = document.getElementById("fileInput");
  const folderInput = document.getElementById("folderInput");
  const btnPilihFile = document.getElementById("btnPilihFile");
  const btnPilihFolder = document.getElementById("btnPilihFolder");
  const fileListWrap = document.getElementById("fileListWrap");
  const fileListUl = document.getElementById("fileListUl");
  const fileCount = document.getElementById("fileCount");
  const btnKosongkanSemua = document.getElementById("btnKosongkanSemua");
  const btnProses = document.getElementById("btnProses");
  const btnUnduh = document.getElementById("btnUnduh");
  const btnReset = document.getElementById("btnReset");
  const inputBidang = document.getElementById("inputBidang");
  const progressWrap = document.getElementById("progressWrap");
  const progressFill = document.getElementById("progressFill");
  const progressLabel = document.getElementById("progressLabel");
  const tambahFileHint = document.getElementById("tambahFileHint");
  const pilihanBatch = document.getElementById("pilihanBatch");
  const btnPilihGabung = document.getElementById("btnPilihGabung");
  const btnPilihBatchBaru = document.getElementById("btnPilihBatchBaru");
  const riwayatList = document.getElementById("riwayatList");

  const statTotal = document.getElementById("statTotal");
  const statBerhasil = document.getElementById("statBerhasil");
  const statGagal = document.getElementById("statGagal");
  const statBaris = document.getElementById("statBaris");

  const dataTableBody = document.getElementById("dataTableBody");
  const logList = document.getElementById("logList");

  const statusBadge = document.getElementById("statusBadge");
  const statusBadgeText = document.getElementById("statusBadgeText");

  let filesTerpilih = [];
  let pollTimer = null;
  let sudahPernahProses = false; // sudah pernah menyelesaikan minimal satu batch?

  function setBadge(mode, text) {
    statusBadge.classList.remove("busy", "error");
    if (mode === "busy") statusBadge.classList.add("busy");
    if (mode === "error") statusBadge.classList.add("error");
    statusBadgeText.textContent = text;
  }

  // ---------- Pemilihan file (dengan tombol hapus per item) ----------
  function renderFileList() {
    if (filesTerpilih.length === 0) {
      fileListWrap.hidden = true;
      pilihanBatch.hidden = true;
      btnProses.disabled = true;
      return;
    }
    fileListWrap.hidden = false;
    fileCount.textContent = filesTerpilih.length;
    fileListUl.innerHTML = "";
    filesTerpilih.slice(0, 300).forEach((f, idx) => {
      const li = document.createElement("li");

      const namaSpan = document.createElement("span");
      namaSpan.className = "nama-file";
      namaSpan.textContent = f.webkitRelativePath || f.name;
      namaSpan.title = f.webkitRelativePath || f.name;

      const btnHapus = document.createElement("button");
      btnHapus.type = "button";
      btnHapus.className = "btn-hapus-file";
      btnHapus.innerHTML = "&times;";
      btnHapus.title = "Batalkan file ini";
      btnHapus.addEventListener("click", () => {
        filesTerpilih.splice(idx, 1);
        renderFileList();
      });

      li.appendChild(namaSpan);
      li.appendChild(btnHapus);
      fileListUl.appendChild(li);
    });

    // kalau sudah pernah ada batch selesai sebelumnya, minta pengguna
    // memilih dulu: gabung ke batch itu, atau mulai batch baru terpisah
    if (sudahPernahProses) {
      pilihanBatch.hidden = false;
      btnProses.hidden = true;
    } else {
      pilihanBatch.hidden = true;
      btnProses.hidden = false;
      btnProses.disabled = false;
    }
  }

  function tambahFile(fileArrayLike) {
    const arrBaru = Array.from(fileArrayLike).filter((f) => f.type === "application/pdf" || f.name.toLowerCase().endsWith(".pdf"));
    // gabung dengan yang sudah dipilih sebelumnya (belum diunggah), hindari
    // duplikat persis (nama + ukuran sama) di level tampilan
    const kunci = (f) => `${f.webkitRelativePath || f.name}__${f.size}`;
    const sudahAda = new Set(filesTerpilih.map(kunci));
    arrBaru.forEach((f) => {
      if (!sudahAda.has(kunci(f))) {
        filesTerpilih.push(f);
        sudahAda.add(kunci(f));
      }
    });
    renderFileList();
  }

  btnPilihFile.addEventListener("click", () => fileInput.click());
  btnPilihFolder.addEventListener("click", () => folderInput.click());
  fileInput.addEventListener("change", (e) => { tambahFile(e.target.files); e.target.value = ""; });
  folderInput.addEventListener("change", (e) => { tambahFile(e.target.files); e.target.value = ""; });

  btnKosongkanSemua.addEventListener("click", () => {
    filesTerpilih = [];
    renderFileList();
  });

  ["dragenter", "dragover"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.add("dragover");
    })
  );
  ["dragleave", "drop"].forEach((evt) =>
    dropZone.addEventListener(evt, (e) => {
      e.preventDefault();
      dropZone.classList.remove("dragover");
    })
  );
  dropZone.addEventListener("drop", (e) => {
    if (e.dataTransfer.files && e.dataTransfer.files.length) {
      tambahFile(e.dataTransfer.files);
    }
  });

  // ---------- Unggah lalu proses ----------
  // resetDulu = true  -> "Buat batch baru terpisah": batch yang sedang
  //                      berjalan ditutup dulu (masuk riwayat), baru unggah
  // resetDulu = false -> "Gabungkan": file baru ditambahkan ke batch yang
  //                      sedang berjalan (perilaku unggah bertahap biasa)
  async function unggahDanProses(resetDulu) {
    if (filesTerpilih.length === 0) return;

    pilihanBatch.hidden = true;
    btnProses.hidden = false;
    btnProses.disabled = true;
    btnProses.textContent = "Mengunggah…";
    setBadge("busy", "Mengunggah file…");

    try {
      if (resetDulu) {
        await fetch("/api/reset", { method: "POST" });
        sudahPernahProses = false;
        btnUnduh.hidden = true;
        btnReset.hidden = true;
        if (tambahFileHint) tambahFileHint.hidden = true;
        statTotal.textContent = "0";
        statBerhasil.textContent = "0";
        statGagal.textContent = "0";
        statBaris.textContent = "0";
        dataTableBody.innerHTML = '<tr class="empty-row"><td colspan="9">Belum ada data. Unggah file PDF untuk memulai.</td></tr>';
        logList.innerHTML = '<li class="log-empty">Tidak ada catatan kesalahan.</li>';
        await muatRiwayat();
      }

      const formData = new FormData();
      filesTerpilih.forEach((f) => formData.append("files", f));

      const res = await fetch("/api/upload", { method: "POST", body: formData });
      const data = await res.json();
      if (!data.ok) {
        alert("Gagal mengunggah: " + (data.pesan || "unknown error"));
        btnProses.disabled = false;
        btnProses.textContent = sudahPernahProses ? "Proses File Baru" : "Proses Semua File";
        setBadge("error", "Gagal unggah");
        return;
      }
      statTotal.textContent = data.total_file;
      progressWrap.hidden = false;
      progressLabel.textContent = "Memproses file baru…";
      btnProses.textContent = "Memproses…";
      btnUnduh.hidden = true;
      setBadge("busy", "Memproses file…");

      const resProcess = await fetch("/api/process", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bidang_override: inputBidang.value.trim() }),
      });
      const dataProcess = await resProcess.json();
      if (!dataProcess.ok) {
        alert("Gagal memulai proses: " + (dataProcess.pesan || "unknown error"));
        btnProses.disabled = false;
        btnProses.textContent = sudahPernahProses ? "Proses File Baru" : "Proses Semua File";
        setBadge("error", "Gagal memproses");
        return;
      }

      filesTerpilih = [];
      fileInput.value = "";
      folderInput.value = "";
      renderFileList();

      mulaiPolling();
    } catch (err) {
      alert("Terjadi kesalahan jaringan lokal: " + err);
      btnProses.disabled = false;
      btnProses.textContent = sudahPernahProses ? "Proses File Baru" : "Proses Semua File";
      setBadge("error", "Terjadi kesalahan");
    }
  }

  btnProses.addEventListener("click", () => unggahDanProses(false));
  btnPilihGabung.addEventListener("click", () => unggahDanProses(false));
  btnPilihBatchBaru.addEventListener("click", () => unggahDanProses(true));

  function renderPreview(rows) {
    if (!rows || rows.length === 0) return;
    dataTableBody.innerHTML = "";
    rows.forEach((r) => {
      const tr = document.createElement("tr");
      ["Nama", "NIP", "Golongan", "Tanggal", "Jam Masuk", "Jam Keluar", "Pulang Telat", "Jumlah Jam Kerja", "Keterangan"].forEach((k) => {
        const td = document.createElement("td");
        td.textContent = r[k] ?? "";
        tr.appendChild(td);
      });
      dataTableBody.appendChild(tr);
    });
  }

  function renderLog(log) {
    if (!log || log.length === 0) {
      logList.innerHTML = '<li class="log-empty">Tidak ada catatan kesalahan.</li>';
      return;
    }
    logList.innerHTML = "";
    log
      .slice()
      .reverse()
      .forEach((item) => {
        const li = document.createElement("li");
        li.innerHTML = `<span class="log-file">${item.file}</span><span class="log-msg">${item.pesan}</span>`;
        logList.appendChild(li);
      });
  }

  // ---------- Riwayat batch (bisa diunduh ulang) ----------
  async function muatRiwayat() {
    try {
      const res = await fetch("/api/riwayat");
      const data = await res.json();
      const daftar = data.riwayat || [];
      if (daftar.length === 0) {
        riwayatList.innerHTML = '<li class="riwayat-empty">Belum ada batch yang selesai diproses.</li>';
        return;
      }
      riwayatList.innerHTML = "";
      daftar.forEach((item) => {
        const li = document.createElement("li");
        const info = document.createElement("div");
        info.className = "riwayat-info";
        info.innerHTML = `<b>${item.jumlah_pegawai} pegawai</b> &middot; ${item.jumlah_baris} baris &middot; ${item.berhasil} berhasil${item.gagal ? `, ${item.gagal} bermasalah` : ""}
          <span class="riwayat-meta">Selesai ${item.waktu}${item.bidang && item.bidang !== "-" ? " &middot; Bidang " + item.bidang : ""}</span>`;
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "btn-unduh-riwayat";
        btn.textContent = "Unduh";
        btn.addEventListener("click", () => {
          window.location.href = `/api/download-riwayat/${encodeURIComponent(item.nama_file)}`;
        });
        li.appendChild(info);
        li.appendChild(btn);
        riwayatList.appendChild(li);
      });
    } catch (err) {
      // diamkan - riwayat bukan fitur kritis
    }
  }

  function mulaiPolling() {
    if (pollTimer) clearInterval(pollTimer);
    pollTimer = setInterval(async () => {
      const res = await fetch("/api/status");
      const s = await res.json();

      statTotal.textContent = s.total_file;
      statBerhasil.textContent = s.berhasil;
      statGagal.textContent = s.gagal;
      statBaris.textContent = s.total_baris;

      const pct = s.total_file ? Math.round((s.diproses / s.total_file) * 100) : 0;
      progressFill.style.width = pct + "%";
      progressLabel.textContent = `Memproses ${s.diproses} dari ${s.total_file} file (kumulatif)… (${pct}%)`;

      renderPreview(s.preview);
      renderLog(s.log);

      if (s.status === "done") {
        clearInterval(pollTimer);
        sudahPernahProses = true;
        progressLabel.textContent = `Selesai — ${s.berhasil} berhasil, ${s.gagal} bermasalah/duplikat dari total ${s.total_file} file.`;

        btnProses.hidden = true;
        pilihanBatch.hidden = true;
        if (s.siap_unduh) btnUnduh.hidden = false;
        btnReset.hidden = false;
        if (tambahFileHint) tambahFileHint.hidden = false;
        setBadge(s.gagal > 0 ? "error" : null, s.gagal > 0 ? "Selesai dengan catatan" : "Selesai");
        muatRiwayat();
      }
    }, 700);
  }

  btnUnduh.addEventListener("click", () => {
    window.location.href = "/api/download";
  });

  btnReset.addEventListener("click", async () => {
    await fetch("/api/reset", { method: "POST" });
    filesTerpilih = [];
    fileInput.value = "";
    folderInput.value = "";
    renderFileList();
    statTotal.textContent = "0";
    statBerhasil.textContent = "0";
    statGagal.textContent = "0";
    statBaris.textContent = "0";
    progressWrap.hidden = true;
    progressFill.style.width = "0%";
    sudahPernahProses = false;
    btnProses.hidden = false;
    btnProses.disabled = true;
    btnProses.textContent = "Proses Semua File";
    pilihanBatch.hidden = true;
    btnUnduh.hidden = true;
    btnReset.hidden = true;
    if (tambahFileHint) tambahFileHint.hidden = true;
    dataTableBody.innerHTML = '<tr class="empty-row"><td colspan="9">Belum ada data. Unggah file PDF untuk memulai.</td></tr>';
    logList.innerHTML = '<li class="log-empty">Tidak ada catatan kesalahan.</li>';
    inputBidang.value = "";
    setBadge(null, "Siap");
    muatRiwayat();
  });

  // ---------- Sinkronkan tampilan dengan status server saat halaman dibuka ----------
  // (penting kalau pengguna me-refresh browser di tengah sesi - supaya kartu
  // statistik & tombol tidak "lupa" progres yang sudah ada di server)
  async function muatStatusAwal() {
    try {
      const res = await fetch("/api/status");
      const s = await res.json();
      if (s.total_file > 0) {
        statTotal.textContent = s.total_file;
        statBerhasil.textContent = s.berhasil;
        statGagal.textContent = s.gagal;
        statBaris.textContent = s.total_baris;
        renderPreview(s.preview);
        renderLog(s.log);
        if (s.status === "done") {
          sudahPernahProses = true;
          btnProses.hidden = true;
          if (s.siap_unduh) btnUnduh.hidden = false;
          btnReset.hidden = false;
          if (tambahFileHint) tambahFileHint.hidden = false;
          setBadge(s.gagal > 0 ? "error" : null, s.gagal > 0 ? "Selesai dengan catatan" : "Selesai");
        } else if (s.status === "processing") {
          progressWrap.hidden = false;
          btnReset.hidden = false;
          setBadge("busy", "Memproses file…");
          mulaiPolling();
        }
      }
    } catch (err) {
      // diamkan - kalau gagal, cukup mulai dari tampilan kosong seperti biasa
    }
  }

  // muat riwayat & status begitu halaman dibuka
  muatRiwayat();
  muatStatusAwal();
})();
