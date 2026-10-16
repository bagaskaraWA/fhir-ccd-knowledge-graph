# -*- coding: utf-8 -*-
"""Label ringkas berbahasa Indonesia untuk tiap rekomendasi yang dinilai.

Disusun dari teks panduan AHA/ACC CCD 2023 pada muatan fakta, bukan dari prosa model
bahasa. Bentuknya sengaja dibuat sependek mungkin dan diawali kata kerja tindakan, sesuai
permintaan pembimbing klinis: alasan lengkapnya sudah ada pada bagian rationale dan tidak
perlu diulang di dalam tabel penilaian.

Ke-21 rekomendasi di bawah meliputi seluruh baris penilaian pada 30 pasien.

KELOMPOK mengikuti kolom pada templat pembimbing:
    cek       -- Cek/stop penggunaan          (safetyFlags, COR 3)
    tata      -- Tatalaksana yang disarankan  (applicable, interventionType CarePlan)
    obat      -- Terapi medikamentosa         (applicable, interventionType Medication)
"""

LABEL = {
    # ---- Cek/stop penggunaan -------------------------------------------------
    "APT:10": ("cek", "Hentikan NSAID kronis — meningkatkan risiko kardiovaskular "
                      "dan perdarahan"),
    "APT:7":  ("cek", "Klopidogrel ditambahkan pada aspirin tanpa ACS atau indikasi DAPT "
                      "terkait PCI — tidak bermanfaat"),
    "APT:9":  ("cek", "Prasugrel pada riwayat stroke/TIA/ICH — risiko perdarahan "
                      "berat atau fatal"),
    "BB:4":   ("cek", "Penyekat beta tanpa riwayat infark miokard atau LVEF ≤50% "
                      "— tidak menurunkan MACE"),
    "SHA:3":  ("cek", "Penghambat PDE5 bersama nitrat — risiko hipotensi berat"),

    # ---- Tatalaksana ---------------------------------------------------------
    "BB:3":   ("tata", "Tinjau ulang indikasi penyekat beta jangka panjang (>1 tahun)"),
    "BPM:2":  ("tata", "Target tekanan darah <130/<80 mmHg"),
    "CR:1:1": ("tata", "Rujuk ke program rehabilitasi jantung"),
    "WM:2":   ("tata", "Konseling diet, gaya hidup, dan target penurunan berat badan"),
    "WM:4":   ("tata", "Rujuk untuk pertimbangan operasi bariatrik"),

    # ---- Terapi medikamentosa ------------------------------------------------
    "APT:4":  ("obat", "Perpanjang DAPT melebihi 12 bulan, hingga 3 tahun"),
    "APT:5":  ("obat", "Tambahkan vorapaxar pada aspirin"),
    "APT:6":  ("obat", "DAPT pascaCABG untuk mencegah oklusi graft vena safena"),
    "APT:11": ("obat", "Bila perlu antikoagulan oral: DAPT 1–4 minggu, lalu "
                       "klopidogrel tunggal 6 bulan, bersama DOAC"),
    "APT:12": ("obat", "Bila perlu antikoagulan oral: lanjutkan aspirin bersama "
                       "klopidogrel hingga 1 bulan"),
    "APT:13": ("obat", "Bila perlu antikoagulan oral: hentikan aspirin, lanjutkan DOAC "
                       "tunggal"),
    "BPM:3":  ("obat", "Antihipertensi lini pertama: penghambat ACE, ARB, atau "
                       "penyekat beta"),
    "SGLT2:1": ("obat", "Penghambat SGLT2 atau agonis reseptor GLP-1 (diabetes tipe 2)"),
    "SGLT2:4": ("obat", "Penghambat SGLT2 (gagal jantung, LVEF ≤40%)"),
    "SGLT2:6": ("obat", "Penghambat SGLT2 (gagal jantung, LVEF >40%)"),
    "WM:3":   ("obat", "Agonis reseptor GLP-1, utamakan semaglutid"),
}

# Baris cek/stop pada lembar telaah ditulis
# "Cek/hentikan penggunaan <obat> pada pasien — <akibat>",
# mengikuti contoh yang diberikan penulis pada 26 September 2026. <obat> adalah nama sediaan
# apa adanya dari rekam medis; <akibat> diambil dari bagian LABEL sesudah tanda pisah
# terakhir, supaya kata-katanya tidak tersimpan di dua tempat. Syarat populasi pada LABEL
# (misalnya "pada riwayat stroke/TIA/ICH") sengaja tidak ikut ditampilkan.
#
# SHA:3 satu-satunya pengecualian. Yang berbahaya adalah kombinasinya, bukan nitratnya, jadi
# "Cek/hentikan penggunaan Nitroglycerin ... — risiko hipotensi berat" akan menyatakan hal
# yang keliru. Keterangan kombinasinya karena itu dipertahankan.
CEK_SISIPAN = {"SHA:3": " bersama penghambat PDE5"}


def teks_cek(rec_id, obat):
    """Teks kolom Rekomendasi untuk satu baris cek/stop."""
    rid = rec_id.replace("CCD-2023:", "")
    akibat = LABEL[rid][1].rsplit(" — ", 1)[1]
    return "Cek/hentikan penggunaan %s%s pada pasien — %s" % (
        obat, CEK_SISIPAN.get(rid, ""), akibat)


# Istilah tampilan. Penulis meminta "beta blocker" alih-alih "penyekat beta", dan "CKD"
# alih-alih "PGK", pada lembar telaah (27 September 2026); "saphenous vein graft occlusion"
# pada label APT:6 berasal dari suntingan tangan penulis pada hari yang sama, dicatat di
# sini agar .csv dan kunci ikut sama dengan .docx. Penggantian ini diterapkan pada
# teks yang dilihat penilai -- kesimpulan dan kolom Rekomendasi, pada .docx maupun .csv --
# sebagai lapisan terakhir, sehingga LABEL di atas dan terjemahan setia pada
# kesimpulan_id.py tetap utuh dan tetap dapat dipakai untuk mengenali bentuk lama pada
# lembar yang belum diperbarui.
ISTILAH = (("Penyekat beta", "Beta blocker"), ("penyekat beta", "beta blocker"),
           ("PGK", "CKD"),
           ("oklusi graft vena safena", "saphenous vein graft occlusion"))


def istilah(teks):
    for lama, baru in ISTILAH:
        teks = teks.replace(lama, baru)
    return teks


JUDUL = {"cek": "Cek/stop penggunaan",
         "tata": "Tatalaksana yang disarankan",
         "obat": "Terapi medikamentosa yang disarankan"}

URUT = {"cek": 0, "tata": 1, "obat": 2}

# Observasi yang menjadi syarat rekomendasi di atas. Seluruhnya SELALU ditampilkan pada
# vinyet, termasuk yang tidak pernah diukur: rekomendasi seperti BB:4 justru menyala karena
# LVEF tidak ada, sehingga penilai harus dapat membedakan "tidak diukur" dari "tidak
# ditampilkan". Kata kuncinya mengikuti nama LOINC yang benar-benar dipakai Synthea --
# LDL, misalnya, tersimpan sebagai "Cholesterol in LDL", bukan "low density lipoprotein".
OBS_KUNCI = (
    ("LVEF", ("ejection fraction",)),
    ("LDL", ("cholesterol in ldl",)),
    ("Trigliserida", ("triglyceride",)),
    ("BMI", ("body mass index",)),
    ("Tekanan darah", ("blood pressure",)),
    ("Status merokok", ("tobacco smoking",)),
)


def label(rec_id):
    """recId lengkap atau pendek -> (kelompok, teks). None bila tidak dikenal."""
    return LABEL.get(rec_id.replace("CCD-2023:", ""))
