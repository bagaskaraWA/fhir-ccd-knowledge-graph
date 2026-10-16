# -*- coding: utf-8 -*-
r"""Rakit dan periksa folder kiriman untuk tiap penilai.

Paket kini hanya memuat tiga berkas per penilai: panduan, lembar telaah Word, dan
padanannya dalam CSV. Rekam medis lengkap TIDAK disertakan -- atas keputusan pembimbing
klinis, penilaian dilakukan semata-mata atas kesimpulan yang disusun sistem.

Skrip ini juga membersihkan sisa rancangan lama (buku penilaian Likert 321 halaman,
formulir Likert, dan salinan rekam medis per pasien) supaya tidak ada berkas usang yang
ikut terkirim dan membingungkan penilai.

    python telaah-klinisi/buat_telaah.py          # menulis telaah-<R>.docx + .csv
    python telaah-klinisi/buat_panduan_docx.py    # menulis panduan-penilaian.docx
    python telaah-klinisi/siapkan_kiriman.py      # menyalin panduan + membersihkan
"""
import io
import os
import shutil
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.join(BASE, "telaah-klinisi")
KIRIM = os.path.join(HERE, "kirim")
PANDUAN = os.path.join(HERE, "panduan-penilaian.docx")
PENILAI = ("R1", "R2")

# Sisa rancangan lama yang harus disingkirkan dari folder kiriman.
USANG_BERKAS = ("panduan-penilaian.md", "buku-penilaian-%s.docx", "formulir-%s.csv")
USANG_FOLDER = ("berkas-pasien",)

# Yang harus ada pada paket akhir.
WAJIB = ("panduan-penilaian.docx", "telaah-%s.docx", "telaah-%s.csv")


def main():
    if not os.path.exists(PANDUAN):
        sys.exit("panduan-penilaian.docx belum ada -- jalankan buat_panduan_docx.py dahulu.")

    dibersihkan = 0
    for r in PENILAI:
        out = os.path.join(KIRIM, r)
        if not os.path.isdir(out):
            sys.exit("folder %s belum ada -- jalankan buat_telaah.py dahulu." % out)

        for pola in USANG_BERKAS:
            p = os.path.join(out, pola % r if "%s" in pola else pola)
            if os.path.exists(p):
                os.remove(p); dibersihkan += 1
        for nama in USANG_FOLDER:
            p = os.path.join(out, nama)
            if os.path.isdir(p):
                n = sum(len(f) for _, _, f in os.walk(p))
                shutil.rmtree(p); dibersihkan += n

        shutil.copy2(PANDUAN, os.path.join(out, "panduan-penilaian.docx"))

    print("berkas usang dihapus : %d" % dibersihkan)
    print()

    kurang = []
    for r in PENILAI:
        out = os.path.join(KIRIM, r)
        isi = sorted(os.listdir(out))
        for pola in WAJIB:
            nama = pola % r if "%s" in pola else pola
            if nama not in isi:
                kurang.append("%s/%s" % (r, nama))
        print("%s : %s" % (r, ", ".join(isi)))

    if kurang:
        print("\nBELUM LENGKAP: %s" % ", ".join(kurang))
        return 1

    # Hitung baris penilaian sebagai pemeriksaan akhir.
    for r in PENILAI:
        p = os.path.join(KIRIM, r, "telaah-%s.csv" % r)
        n = sum(1 for _ in io.open(p, encoding="utf-8-sig")) - 1
        print("\n%s : %d baris penilaian" % (r, n))

    print("\nPaket siap dikirim. Ingatkan penilai: jangan berdiskusi sebelum selesai.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
