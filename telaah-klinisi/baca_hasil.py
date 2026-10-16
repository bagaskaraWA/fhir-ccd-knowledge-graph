# -*- coding: utf-8 -*-
r"""Baca lembar telaah yang sudah diisi klinisi menjadi satu tabel panjang.

    python telaah-klinisi/baca_hasil.py          # menulis hasil/penilaian.csv dan melapor

Setiap penilai menandai pilihannya dengan caranya sendiri, dan ketiganya dikenali:
  - mengklik kotak centang Word (w14:checkbox),
  - mengganti ☐ dengan tanda lain (☑, ☒, ✓, ✔, simbol Wingdings),
  - menghapus dua pilihan lain sehingga hanya label pilihannya yang tersisa.

Baris dipetakan ke rekomendasinya lewat kunci-telaah.csv menurut nomor pasien dan urutan baris,
lalu teks rekomendasinya dicocokkan; lembar yang teksnya berubah ditolak. Sel yang tidak dapat
dibaca dengan pasti (lebih dari satu tanda, atau label yang tidak dikenali) dilaporkan dan
ditulis sebagai "?" agar diputuskan dengan membaca lembarnya.
"""
import csv
import io
import os
import re
import sys
from collections import Counter, OrderedDict

from docx import Document
from docx.oxml.ns import qn
from docx.table import Table

sys.stdout.reconfigure(encoding="utf-8")
HERE = os.path.dirname(os.path.abspath(__file__))
HASIL = os.path.join(HERE, "hasil")
KUNCI = os.path.join(HERE, "kunci-telaah.csv")
KELUARAN = os.path.join(HASIL, "penilaian.csv")

# berkas -> (kode penilai, keterangan, pasien yang dinyatakan diisi). Kodenya sama dengan
# kode pada naskah (Subbab 3.6.6); nama berkas tidak ikut ke data keluaran. Lembar aslinya
# tidak dikomit karena properti berkasnya dapat memuat nama penilai.
PENILAI = OrderedDict([
    ("telaah junior.docx", ("A", "SpJP", range(1, 16))),
    ("telaah phd.docx", ("B", "dokter umum, mahasiswa program doktor", range(1, 11))),
    ("telaah senior.docx", ("C", "SpJP senior", range(1, 2))),
])
LABEL = ("Tidak dapat dinilai", "Belum tepat", "Tepat")      # terpanjang lebih dahulu
KOSONG = "☐"
TANDA = set("☑☒✓✔✅■▣")
SYM_TANDA = {"F0FE", "F0FD", "F078", "F0FC", "F0FB"}       # Wingdings: kotak bertanda, centang
SYM_KOSONG = {"F0A8", "F06F", "F071"}
JUDUL_PASIEN = re.compile(r"^(\d+)\.\s")
PENGENAL = re.compile(r"pengenal ([0-9a-f]{8})\b")


def norm(t):
    return " ".join(t.replace(" ", " ").split())


def token_sel(cell):
    """Urutan token sel Penilaian: ('kotak', True/False) atau ('teks', str)."""
    out = []
    w14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
    for p in cell.paragraphs:
        for el in p._p.iter():
            if el.tag == qn("w:sdt"):
                cb = el.find(".//" + w14 + "checked")
                if cb is not None:
                    out.append(("kotak", cb.get(w14 + "val") in ("1", "true")))
            elif el.tag == qn("w:sym"):
                ch = (el.get(qn("w:char")) or "").upper()
                if ch in SYM_TANDA or ch in SYM_KOSONG:
                    out.append(("kotak", ch in SYM_TANDA))
            elif el.tag == qn("w:t"):
                if any(a.tag == qn("w:sdtContent") for a in el.iterancestors()):
                    continue                         # glyph kotak centang Word: sudah dihitung
                for ch in re.split(r"([☐☑☒✓✔✅■▣])", el.text or ""):
                    if ch == KOSONG:
                        out.append(("kotak", False))
                    elif ch in TANDA:
                        out.append(("kotak", True))
                    elif ch:
                        out.append(("teks", ch))
        out.append(("teks", " "))
    return out


def baca_sel(cell):
    """Kembalikan (penilaian, cara). penilaian: label, "" bila kosong, "?" bila meragukan."""
    tok = token_sel(cell)
    # gabungkan teks yang mengikuti setiap kotak
    segmen, cur = [], None
    awal = ""
    for jenis, v in tok:
        if jenis == "kotak":
            cur = [v, ""]
            segmen.append(cur)
        elif cur is None:
            awal += v
        else:
            cur[1] += v
    bertanda = [s for s in segmen if s[0]]
    if len(bertanda) > 1:
        return "?", "lebih dari satu tanda"
    if len(bertanda) == 1:
        teks = norm(bertanda[0][1])
        for lab in LABEL:
            if teks.startswith(lab):
                return lab, "tanda"
        return "?", "label tidak dikenali: %r" % teks
    sisa = norm(awal + " ".join(s[1] for s in segmen))
    if sisa in LABEL and len(segmen) == 0:
        return sisa, "pilihan lain dihapus"
    if sisa == "Tepat Belum tepat Tidak dapat dinilai":
        return "", "kosong"
    return "?", "tidak dikenali: %r" % sisa


def baca_lembar(path):
    doc = Document(path)
    no, pid8, out = None, None, []
    for blok in doc.element.body.iterchildren():
        if blok.tag == qn("w:p"):
            teks = "".join(x.text or "" for x in blok.iter(qn("w:t")))
            m = JUDUL_PASIEN.match(teks)
            if m and blok.find(".//" + qn("w:pStyle")) is not None:
                no, pid8 = int(m.group(1)), None
            m = PENGENAL.search(teks)
            if m:
                pid8 = m.group(1)
        elif blok.tag == qn("w:tbl"):
            t = Table(blok, doc._body)
            hdr = [c.text.strip() for c in t.rows[0].cells]
            if "Rekomendasi" not in hdr:
                continue
            kr = hdr.index("Rekomendasi")
            kp = next(i for i, h in enumerate(hdr) if h.startswith("Penilaian"))
            for row in t.rows[1:]:
                c = row.cells
                nilai, cara = baca_sel(c[kp])
                out.append(dict(no=no, pid8=pid8, rekomendasi=norm(c[kr].text),
                                penilaian=nilai, cara=cara, saran=norm(c[kp + 1].text)))
    return out


def main():
    kunci = list(csv.DictReader(io.open(KUNCI, encoding="utf-8-sig")))
    baris, masalah = [], []
    for berkas, (kode, ket, cakupan) in PENILAI.items():
        lembar = baca_lembar(os.path.join(HASIL, berkas))
        if len(lembar) != len(kunci):
            sys.exit("%s: %d baris, kunci %d -- berhenti." % (berkas, len(lembar), len(kunci)))
        for k, (a, b) in enumerate(zip(lembar, kunci)):
            if (str(a["no"]) != b["no"] or a["pid8"] != b["pasien"][:8]
                    or a["rekomendasi"] != norm(b["rekomendasi"])):
                sys.exit("%s baris %d tidak cocok dengan kunci: %r / %r -- berhenti."
                         % (berkas, k + 1, a["rekomendasi"], b["rekomendasi"]))
            if a["penilaian"] == "?":
                masalah.append("%s pasien %s, %s: %s" % (kode, a["no"], b["recId"], a["cara"]))
            if a["no"] in cakupan and a["penilaian"] == "":
                masalah.append("%s pasien %s, %s: kosong di dalam cakupan" % (kode, a["no"], b["recId"]))
            if a["no"] not in cakupan and a["penilaian"] not in ("",):
                masalah.append("%s pasien %s, %s: terisi di luar cakupan" % (kode, a["no"], b["recId"]))
            baris.append(OrderedDict(penilai=kode, keterangan=ket, no=b["no"], pasien=b["pasien"],
                                     kelompok=b["kelompok"], recId=b["recId"], cor=b["cor"],
                                     rekomendasi=b["rekomendasi"], penilaian=a["penilaian"],
                                     saran=a["saran"], cara=a["cara"]))
        isi = [r for r in baris if r["penilai"] == kode and r["penilaian"]]
        c = Counter(r["penilaian"] for r in isi)
        pasien = sorted({int(r["no"]) for r in isi})
        print("%-7s %-34s %3d baris terisi, pasien %s | %s | cara: %s"
              % (kode, ket, len(isi), "%d-%d" % (pasien[0], pasien[-1]) if pasien else "-",
                 ", ".join("%s %d" % kv for kv in sorted(c.items())),
                 dict(Counter(r["cara"] for r in isi))))
    buf = io.StringIO(newline="")
    w = csv.DictWriter(buf, fieldnames=list(baris[0].keys()))
    w.writeheader()
    w.writerows(baris)
    open(KELUARAN, "wb").write(("﻿" + buf.getvalue()).encode("utf-8"))
    print("ditulis:", KELUARAN)
    print("perlu diperiksa (%d):" % len(masalah))
    for m in masalah:
        print("  - " + m)


if __name__ == "__main__":
    main()
