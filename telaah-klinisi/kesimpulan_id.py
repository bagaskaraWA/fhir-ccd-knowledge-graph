# -*- coding: utf-8 -*-
"""Terjemahan bahasa Indonesia atas bagian "Kesimpulan generator" (BOTTOM LINE) ringkasan.

Ringkasan dibangkitkan model bahasa dalam bahasa Inggris. Atas permintaan, kesimpulan itu
diterjemahkan untuk penilai. Terjemahan disimpan di sini, bukan hanya di dalam berkas Word,
agar teks yang benar-benar dilihat penilai tercatat dan dapat ditelusuri kembali ke sumbernya.

Prinsip penerjemahan -- penting karena penilai menilai rekomendasi sistem berdasarkan teks ini:
  * SETIA, bukan memperbaiki. Setiap klaim sumber dipertahankan, termasuk yang mungkin keliru
    secara klinis; terjemahan tidak menambah, mengurangi, atau melunakkan isi.
  * Angka, target tekanan darah, kutipan dalam kurung siku ([CR:1:1, COR1] dan sejenisnya),
    serta kelas rekomendasi disalin apa adanya.
  * Istilah mengikuti label pada tabel penilaian (label_rekomendasi.py): penyekat beta,
    penghambat PDE5, penghambat SGLT2, agonis reseptor GLP-1, rehabilitasi jantung, cek/stop.
  * Nama obat memakai ejaan Indonesia: klopidogrel, nitrogliserin, metoprolol suksinat,
    naproksen. Singkatan klinis yang lazim dibiarkan: CCD, CABG, STEMI, NSTEMI, PCI, ACS,
    GDMT, MACE, LVEF, ESRD, BMI. CKD menjadi PGK.
  * EYD V: "pasca-CABG" memakai tanda hubung (Penulisan Kata, Kata Turunan 1.c: kata
    berhuruf awal kapital yang mendapat bentuk terikat dirangkaikan dengan tanda hubung);
    rentang stadium memakai tanda pisah, "stadium 1—2" (Tanda Pisah 3: di antara dua
    bilangan yang berarti "sampai dengan").

Diterjemahkan oleh Claude (claude-opus-5-5) pada 26 September 2026 untuk penilai R1.

Kunci = delapan karakter awal pengenal pasien, sama dengan yang tercetak pada lembar telaah.
"""

TERJEMAHAN = {
    "01dc6d0f": (
        "Pasien penyakit jantung koroner kronis dengan riwayat infark miokard (termasuk satu "
        "kejadian STEMI), penyakit jantung iskemik yang sudah tegak, hipertensi, obesitas, PGK "
        "stadium 3, dan penyakit ginjal diabetik/proteinuria. Tindakan prioritas tertinggi: "
        "rujuk ke program rehabilitasi jantung [CR:1:1, COR1]. Perhatian keamanan utama: "
        "pasien ini menggunakan prasugrel dan metoprolol, keduanya ditandai untuk populasi ini. "
        "Periksa tanda di bawah sebelum melanjutkan salah satu dari keduanya."),
    "0333a5c9": (
        "Pasien penyakit jantung koroner kronis dengan riwayat infark miokard, hipertensi "
        "esensial, diabetes tipe 2, dan obesitas berat (BMI 40+), disertai sejumlah "
        "komorbiditas (PGK, status pascatransplantasi ginjal, penyakit Alzheimer). Tindakan "
        "prioritas tertinggi: optimalkan GDMT penurun tekanan darah dan tambahkan penghambat "
        "SGLT2/agonis reseptor GLP-1 untuk diabetes, serta pastikan rujukan rehabilitasi "
        "jantung. Perhatian keamanan utama: nitrogliserin semprot sama sekali tidak boleh "
        "dikombinasikan dengan penghambat PDE5 (risiko hipotensi berat)."),
    "03b03863": (
        "Pasien penyakit jantung koroner kronis dengan riwayat CABG, penyakit jantung "
        "iskemik, diabetes tipe 2, hipertensi esensial, obesitas (BMI 30+), PGK stadium 1, dan "
        "hiperlipidemia. Tindakan utama: rujuk ke program rehabilitasi jantung (indikasi "
        "pasca-CABG) [CCD-2023:CR:1:1, COR 1]. Perhatian keamanan utama: pasien saat ini "
        "menggunakan tiga obat (metoprolol suksinat, klopidogrel, nitrogliserin semprot) yang "
        "masing-masing ditandai oleh rekomendasi tanpa manfaat/berbahaya di bawah; tinjau "
        "sebelum dilanjutkan."),
    "04287b67": (
        "Pasien CCD dengan riwayat CABG, diabetes tipe 2, hipertensi esensial, obesitas, dan "
        "PGK stadium 1—2/penyakit ginjal diabetik. Prioritas utama: rujukan rehabilitasi "
        "jantung, pengendalian tekanan darah yang lebih ketat dengan GDMT, dan pertimbangan "
        "penghambat SGLT2/agonis reseptor GLP-1 untuk menurunkan risiko kardiovaskular terkait "
        "diabetes. Perhatian keamanan utama: daftar obat pasien saat ini (metoprolol "
        "suksinat, klopidogrel, nitrogliserin semprot) cocok dengan tiga rekomendasi tanpa "
        "manfaat/berbahaya yang ditandai dan perlu ditinjau ulang."),
    "05e41fe3": (
        "Pasien dengan CCD yang sudah tegak, disertai riwayat infark miokard dan CABG, NSTEMI "
        "saat ini, penyakit jantung iskemik, hipertensi, diabetes tipe 2, dan obesitas. "
        "Prioritas utama: rujuk ke program rehabilitasi jantung, pastikan tekanan darah "
        "<130/80 dengan GDMT, dan tambahkan penghambat SGLT2/agonis reseptor GLP-1 untuk "
        "menurunkan risiko kardiovaskular pada diabetes. Perhatian keamanan utama: tiga tanda "
        "cek/stop pada obat yang sedang digunakan (nitrogliserin, prasugrel, metoprolol "
        "suksinat), lihat di bawah."),
    "07f42172": (
        "Pasien CCD dengan riwayat infark miokard/NSTEMI dan penyakit jantung iskemik, dengan "
        "penyulit hipertensi, diabetes tipe 2 dengan keterlibatan ginjal diabetik, PGK, dan "
        "obesitas; obat yang sedang digunakan meliputi prasugrel, propranolol, metoprolol "
        "suksinat, klopidogrel, dan nitrogliserin semprot. Tindakan utama: rujuk ke program "
        "rehabilitasi jantung, optimalkan pengendalian tekanan darah sesuai GDMT, dan "
        "pertimbangkan penghambat SGLT2/agonis reseptor GLP-1 untuk menurunkan risiko "
        "kardiovaskular pada diabetes. Perhatian keamanan utama: regimen penyekat beta dan "
        "antiplatelet saat ini memiliki masalah yang ditandai (penggunaan penyekat beta tanpa "
        "manfaat, kewaspadaan risiko perdarahan prasugrel, risiko interaksi nitrat/PDE5) yang "
        "perlu ditinjau."),
    "093d7bf0": (
        "Pasien dengan CCD yang sudah tegak (riwayat infark miokard, riwayat CABG, penyakit "
        "jantung iskemik), disertai diabetes tipe 2, gagal jantung kronis, dan obesitas. "
        "Prioritas utama: mulai penghambat SGLT2/agonis reseptor GLP-1 untuk manfaat pada "
        "diabetes dan gagal jantung, serta rujuk ke program rehabilitasi jantung. Perhatian "
        "keamanan utama: daftar obat saat ini memuat beberapa obat yang ditandai berbahaya atau "
        "tanpa manfaat (NSAID, nitrat, satu antiplatelet, satu penyekat beta) sehingga perlu "
        "tinjauan obat."),
    "09fd55b4": (
        "Pasien dengan penyakit jantung koroner kronis yang sudah tegak (penyakit jantung "
        "iskemik, riwayat CABG) disertai diabetes tipe 2, hipertensi esensial, PGK stadium 1, "
        "dan hipertrigliseridemia/sindrom metabolik. Prioritas utama: optimalkan tekanan darah "
        "hingga <130/80, pastikan penggunaan penghambat SGLT2/agonis reseptor GLP-1 untuk "
        "menurunkan risiko kardiovaskular terkait diabetes, dan pastikan rujukan rehabilitasi "
        "jantung mengingat riwayat CABG. Perhatian keamanan utama: daftar obat pasien saat ini "
        "memuat empat obat yang ditandai tanpa manfaat atau berbahaya pada CCD (lihat di "
        "bawah), dan masing-masing perlu ditinjau."),
    "0b8fa61e": (
        "Pasien CCD dengan riwayat infark miokard, CABG, dan penyakit jantung iskemik, "
        "disertai hipertensi esensial dan sejumlah komorbiditas (PGK stadium 1—2, penyakit "
        "ginjal diabetik, riwayat kanker, apnea tidur, faktor risiko kesehatan jiwa/sosial). "
        "Tindakan terpenting adalah rujukan rehabilitasi jantung disertai optimalisasi "
        "tekanan darah hingga <130/80 dengan terapi berbasis penghambat ACE/ARB/penyekat beta. "
        "Perhatian keamanan utama: penyekat beta pasien ini ditandai tidak memberikan manfaat "
        "terhadap MACE di luar indikasi yang memenuhi syarat, dan nitrogliserin membawa "
        "peringatan bahaya bila dikombinasikan dengan penghambat PDE5."),
    "1225ac52": (
        "Pasien penyakit jantung koroner kronis dengan penyakit jantung iskemik, hipertensi "
        "esensial, diabetes tipe 2 (dengan keterlibatan ginjal diabetik dan PGK stadium 3), "
        "dan obesitas. Tindakan prioritas: terapi tekanan darah/diabetes sesuai panduan, "
        "konseling pengelolaan berat badan, dan rujukan rehabilitasi jantung. Perhatian "
        "keamanan utama: tiga obat yang sedang digunakan pasien (metoprolol suksinat, "
        "klopidogrel, nitrogliserin) ditandai untuk ditinjau terhadap kriteria di bawah."),
    "1db4196c": (
        "Pasien CCD yang mengalami NSTEMI akut dengan latar belakang riwayat infark miokard, "
        "riwayat CABG, hipertensi, hiperlipidemia, dan obesitas (BMI 30+), disertai PGK "
        "multistadium dan riwayat transplantasi ginjal. Tindakan prioritas tertinggi: rujuk ke "
        "program rehabilitasi jantung dan optimalkan tekanan darah hingga target <130/<80 "
        "dengan GDMT (lini pertama penghambat ACE/ARB/penyekat beta). Perhatian keamanan "
        "utama: pasien saat ini menggunakan prasugrel dan nitrogliserin (semprot dan "
        "sublingual), keduanya membawa tanda cek/stop yang tegas di bawah."),
    "20713969": (
        "Pasien CCD dengan riwayat infark miokard dan CABG, hipertensi esensial, diabetes "
        "tipe 2 (dengan nefropati diabetik/PGK, ESRD, dan status transplantasi ginjal), dan "
        "obesitas. Prioritas utama: rujuk ke program rehabilitasi jantung (COR1) dan "
        "optimalkan terapi tekanan darah dan diabetes sesuai panduan (penghambat SGLT2/GLP-1, "
        "COR1); perhatian keamanan utama adalah mengevaluasi ulang penggunaan penyekat beta "
        "dan klopidogrel saat ini, serta menghindari pemberian bersama nitrat dan penghambat "
        "PDE5."),
    "227e76d8": (
        "Pasien penyakit jantung koroner kronis dengan riwayat infark miokard dan CABG, "
        "hipertensi esensial, obesitas, dan penyakit jantung iskemik, yang saat ini mendapat "
        "terapi penyekat beta, antiplatelet, statin, dan penghambat RAAS. Prioritas utama "
        "adalah rujukan rehabilitasi jantung, pengendalian tekanan darah hingga <130/<80, dan "
        "konseling pengelolaan berat badan; perhatian keamanan utama adalah sekelompok obat "
        "yang sedang digunakan (ibuprofen, nitrogliserin semprot, prasugrel, klopidogrel, "
        "metoprolol suksinat) yang ditandai berbahaya atau tanpa manfaat pada populasi ini."),
    "22f599b6": (
        "Pasien CCD dengan penyakit aterosklerotik yang sudah tegak (penyakit jantung "
        "iskemik, riwayat STEMI/infark miokard, riwayat CABG), hipertensi, penyakit ginjal "
        "diabetik, dan obesitas. Prioritas utama: rujuk ke program rehabilitasi jantung "
        "(COR 1) dan tangani hipertensi hingga target <130/<80 dengan GDMT (COR 1); strategi "
        "antiplatelet perlu mencerminkan riwayat PCI, tetapi setiap regimen yang bergantung "
        "pada antikoagulan oral harus dikonfirmasi secara klinis terlebih dahulu. Perhatian "
        "keamanan utama: interaksi nitrat/penghambat PDE5 (berbahaya) dan kontraindikasi "
        "prasugrel bila ada riwayat stroke/TIA/ICH, ditambah dua tanda tanpa manfaat pada "
        "penggunaan penyekat beta dan klopidogrel."),
    "264e5178": (
        "Pasien CCD dengan penyakit jantung iskemik dan riwayat CABG, disertai hipertensi, "
        "diabetes tipe 2 (dengan penyakit ginjal diabetik), dan obesitas. Prioritas utama: "
        "rujuk ke program rehabilitasi jantung, perketat pengendalian tekanan darah dengan "
        "GDMT, dan mulai penghambat SGLT2 atau agonis reseptor GLP-1 untuk menurunkan risiko "
        "kardiovaskular terkait diabetes. Perhatian keamanan utama: nitrogliserin semprot yang "
        "sedang digunakan memiliki kontraindikasi mutlak dengan penghambat PDE5, dan dua obat "
        "yang sedang digunakan pasien (metoprolol suksinat, klopidogrel) ditandai tidak "
        "terindikasi tanpa pemicu spesifik yang tidak tercatat pada pasien ini."),
    "2845fe64": (
        "Pasien penyakit jantung koroner kronis (penyakit jantung iskemik, riwayat CABG) "
        "dengan hipertensi, diabetes tipe 2 (dengan nefropati/retinopati diabetik), obesitas, "
        "dan hiperlipidemia. Prioritas utama: optimalkan terapi obat penurun tekanan darah dan "
        "tambahkan penghambat SGLT2/agonis reseptor GLP-1 untuk menurunkan MACE terkait "
        "diabetes, ditambah rujukan formal rehabilitasi jantung mengingat riwayat CABG. "
        "Perhatian keamanan utama: tiga obat yang sedang digunakan pasien (metoprolol "
        "suksinat, klopidogrel, nitrogliserin semprot) terkena rekomendasi yang ditandai tanpa "
        "manfaat atau berbahaya dalam konteks ini; verifikasi indikasinya sebelum "
        "dilanjutkan."),
    "2b050f16": (
        "Pasien penyakit jantung koroner kronis (penyakit jantung iskemik, riwayat CABG), "
        "hipertensi esensial, diabetes tipe 2, dan obesitas (BMI 30+), disertai PGK "
        "multistadium/riwayat transplantasi ginjal. Tindakan prioritas: rujukan rehabilitasi "
        "jantung, pengendalian tekanan darah hingga <130/<80, dan penghambat SGLT2/agonis "
        "reseptor GLP-1 untuk diabetes. Perhatian keamanan utama: penyekat beta yang sedang "
        "digunakan (metoprolol suksinat) mungkin tidak memberikan manfaat yang terbukti tanpa "
        "indikasi yang memenuhi syarat, dan nitrogliserin semprot pada daftar obat membawa "
        "risiko hipotensi bila suatu saat dikombinasikan dengan penghambat PDE5."),
    "2bda8853": (
        "Pasien penyakit jantung koroner kronis dengan riwayat CABG, hipertensi esensial, "
        "diabetes tipe 2 (disertai keterlibatan ginjal), dan obesitas. Tindakan prioritas: "
        "rujukan rehabilitasi jantung, optimalisasi target tekanan darah/antihipertensi lini "
        "pertama, penghambat SGLT2/agonis reseptor GLP-1 untuk manfaat kardiovaskular, dan "
        "dukungan pengelolaan berat badan. Perhatian keamanan utama: pasien saat ini "
        "menggunakan klopidogrel dan metoprolol suksinat, keduanya ditandai \"tanpa manfaat\" "
        "dalam konteks ini bila tidak ada indikasi yang memenuhi syarat, ditambah tanda bahaya "
        "untuk naproksen dan peringatan interaksi nitrat."),
    "3756b42c": (
        "Pasien CCD yang kompleks dengan riwayat CABG, penyakit jantung iskemik, gagal "
        "jantung kongestif kronis, hipertensi esensial, diabetes tipe 2, obesitas, dan PGK "
        "(stadium 1—4, menurut temuan berkode). Tindakan terpenting adalah rujukan "
        "rehabilitasi jantung (dipicu riwayat CABG) [CCD-2023:CR:1:1, COR 1], bersama terapi "
        "target tekanan darah/antihipertensi lini pertama, penggunaan penghambat "
        "SGLT2/agonis reseptor GLP-1 (indikasi diabetes dan gagal jantung), serta konseling "
        "pengelolaan berat badan. Perhatian keamanan utama: pasien saat ini menggunakan tiga "
        "obat yang ditandai oleh pernyataan panduan \"tanpa manfaat/berbahaya\", yaitu "
        "metoprolol suksinat, klopidogrel, dan nitrogliserin semprot, yang masing-masing "
        "memerlukan cek/stop."),
    "3875c68d": (
        "Pasien CCD dengan riwayat infark miokard, riwayat CABG, NSTEMI, dan hipertensi, "
        "disertai sejumlah komorbiditas (PGK stadium 1—4/ESRD, status pascatransplantasi "
        "ginjal, penyakit ginjal terkait diabetes). Prioritas utama: rujukan rehabilitasi "
        "jantung, pengendalian tekanan darah hingga <130/80 dengan terapi berbasis penghambat "
        "ACE/ARB/penyekat beta, dan tinjauan strategi antiplatelet/antikoagulan. Perhatian "
        "keamanan utama: dua obat aktif (prasugrel, nitrogliserin) membawa peringatan Kelas 3 "
        "(berbahaya) yang memerlukan cek/stop segera."),
    "51648be0": (
        "Pasien CCD dengan riwayat infark miokard/penyakit jantung iskemik, diabetes tipe 2 "
        "dengan keterlibatan ginjal diabetik, hipertensi, dan obesitas, yang saat ini mendapat "
        "warfarin, statin, penyekat beta, golongan ACE/ARB, dan terapi antiangina. Tindakan "
        "prioritas: rujukan rehabilitasi jantung, pengendalian tekanan darah hingga <130/80 "
        "dengan obat GDMT, penghambat SGLT2/agonis reseptor GLP-1 untuk diabetes, dan "
        "pengelolaan berat badan terstruktur. Perhatian keamanan utama: penyekat beta dan "
        "nitrat yang sedang digunakan membawa peringatan spesifik obat, penggunaan naproksen "
        "kronis ditandai berbahaya, dan prasugrel dikontraindikasikan pada kelompok risiko "
        "yang relevan."),
    "6595b70f": (
        "Pasien CCD dengan riwayat infark miokard/penyakit jantung iskemik, hipertensi "
        "esensial, diabetes tipe 2 (dengan penyakit ginjal diabetik, PGK stadium 3—4/ESRD, "
        "riwayat transplantasi ginjal/menunggu transplantasi ulang), dan obesitas berat "
        "(BMI 40+). Tindakan prioritas: perketat pengendalian tekanan darah, mulai atau "
        "pastikan penghambat SGLT2 atau agonis reseptor GLP-1 untuk manfaat kardiovaskular, "
        "serta rujuk ke program rehabilitasi jantung dan dukungan pengelolaan berat badan. "
        "Perhatian keamanan utama: sediaan nitrogliserin pada daftar obat membawa peringatan "
        "interaksi yang tegas dengan penghambat PDE5, dan prasugrel membawa peringatan risiko "
        "perdarahan; penggunaan metoprolol dan klopidogrel juga perlu diperiksa ulang terhadap "
        "indikasinya."),
    "6b38af11": (
        "Pasien CCD dengan riwayat STEMI, riwayat infark miokard, dan riwayat CABG, disertai "
        "hipertensi, diabetes tipe 2 dengan keterlibatan ginjal, obesitas, PGK, serta riwayat "
        "transplantasi ginjal/terdaftar untuk transplantasi. Tindakan prioritas tertinggi "
        "adalah rujukan rehabilitasi jantung, memperketat tekanan darah hingga <130/80 dengan "
        "GDMT, dan menambahkan penghambat SGLT2 atau agonis reseptor GLP-1 untuk diabetes "
        "dengan manfaat kardiovaskular yang terbukti. Perhatian keamanan utama: pasien ini "
        "menggunakan ibuprofen dan prasugrel, keduanya ditandai berbahaya pada CCD, ditambah "
        "risiko interaksi nitrogliserin semprot dan penyekat beta yang manfaat jangka "
        "panjangnya perlu dinilai ulang."),
    "75409e1a": (
        "Pasien dengan penyakit jantung koroner kronis yang sudah tegak (riwayat infark "
        "miokard, riwayat CABG, penyakit jantung iskemik) disertai hipertensi, obesitas, dan "
        "PGK lanjut/ESRD (pascatransplantasi atau menunggu transplantasi ginjal). Prioritas "
        "utama: rujukan rehabilitasi jantung, pengendalian tekanan darah hingga <130/80 dengan "
        "GDMT, dan konseling pengelolaan berat badan. Perhatian keamanan utama: beberapa obat "
        "yang sedang digunakan (metoprolol suksinat, klopidogrel, naproksen, nitrogliserin "
        "semprot, prasugrel) ditandai tanpa manfaat atau berbahaya dalam konteks tertentu; "
        "tinjau sebelum dilanjutkan."),
    "86d84b1c": (
        "Pasien CCD dengan riwayat infark miokard/STEMI, diabetes tipe 2 (dengan nefropati, "
        "retinopati, dan neuropati diabetik), hipertensi esensial, dan obesitas. Prioritas "
        "utama: rujukan rehabilitasi jantung, pengendalian tekanan darah yang lebih ketat "
        "dengan GDMT, dan penghambat SGLT2 atau agonis reseptor GLP-1 untuk diabetes dengan "
        "manfaat kardiovaskular yang terbukti. Empat obat yang sedang digunakan pasien memicu "
        "tanda keamanan cek/stop (lihat di bawah) dan perlu ditinjau sebelum perubahan lain "
        "dilakukan."),
    "8bb750c8": (
        "Pasien CCD yang kompleks dengan NSTEMI yang baru terjadi, riwayat infark miokard, "
        "riwayat CABG, hipertensi esensial, diabetes tipe 2 (dengan nefropati, neuropati, "
        "retinopati), dan obesitas, disertai beban komorbiditas nonkardiak yang berat "
        "(penyakit Alzheimer, riwayat CVA, nyeri kronis, riwayat masalah kesehatan "
        "jiwa/penggunaan zat). Prioritas utama: rujuk ke program rehabilitasi jantung, "
        "pastikan target tekanan darah dan strategi antihipertensi lini pertama, dan pastikan "
        "terapi diabetes mencakup obat dengan manfaat kardiovaskular yang terbukti. Perhatian "
        "keamanan utama: pasien ini menggunakan prasugrel meskipun memiliki riwayat "
        "stroke/CVA (kontraindikasi yang diakui karena risiko perdarahan), ditambah obat lain "
        "yang ditandai di bawah."),
    "cbf432fc": (
        "Pasien CCD yang kompleks dengan riwayat CABG, hipertensi esensial, diabetes tipe 2 "
        "(dengan nefropati diabetik), gagal jantung kronis, obesitas, dan sindrom metabolik. "
        "Tindakan prioritas: rujuk ke program rehabilitasi jantung (pasca-CABG), perketat "
        "pengendalian tekanan darah dengan GDMT, mulai penghambat SGLT2/agonis reseptor GLP-1 "
        "untuk diabetes, dan tangani obesitas. Perhatian keamanan utama: tiga obat yang sedang "
        "digunakan pasien (metoprolol suksinat, klopidogrel, nitrogliserin semprot) "
        "masing-masing cocok dengan tanda tanpa manfaat/berbahaya di bawah dan perlu diperiksa "
        "pada rekam medis."),
    "d7748b62": (
        "Pasien CCD dengan riwayat infark miokard, riwayat CABG, hipertensi esensial, "
        "obesitas (BMI 30+), PGK stadium 1—2, dan riwayat stroke (CVA), yang saat ini "
        "menggunakan prasugrel, klopidogrel, dua penyekat beta (metoprolol suksinat + "
        "propranolol), dan nitrogliserin semprot. Cek/stop yang paling mendesak adalah "
        "prasugrel pada pasien dengan riwayat stroke (risiko bahaya perdarahan); penggunaan "
        "penyekat beta ganda serta klopidogrel yang ditambahkan pada aspirin tanpa indikasi "
        "ACS/PCI yang jelas juga perlu ditinjau. Di luar tinjauan keamanan, prioritaskan "
        "pengendalian tekanan darah hingga <130/80, optimalisasi antihipertensi lini pertama, "
        "rujukan rehabilitasi jantung, dan konseling pengelolaan berat badan."),
    "d8d734c3": (
        "Pasien penyakit jantung koroner kronis dengan riwayat infark miokard dan CABG, "
        "riwayat NSTEMI, penyakit jantung iskemik, hipertensi, diabetes tipe 2 (dengan "
        "retinopati/PGK/mikroalbuminuria), gagal jantung kronis, dan obesitas. Tindakan "
        "prioritas tertinggi: rujuk ke program rehabilitasi jantung [CCD-2023:CR:1:1, COR 1] "
        "mengingat riwayat infark miokard/CABG, bersama optimalisasi tekanan darah dan "
        "penggunaan penghambat SGLT2/GLP-1 untuk manfaat pada diabetes dan gagal jantung. "
        "Perhatian keamanan utama: pasien ini saat ini menggunakan ibuprofen dan naproksen, "
        "yang membawa tanda bahaya kardiovaskular/perdarahan langsung pada CCD."),
    "e15faae0": (
        "Pasien dengan CCD yang sudah tegak (riwayat infark miokard, riwayat CABG, penyakit "
        "jantung iskemik), hipertensi, diabetes tipe 2 dengan keterlibatan ginjal, dan "
        "obesitas. Tindakan prioritas tertinggi: pastikan target tekanan darah dan regimen "
        "antihipertensi lini pertama, mulai penghambat SGLT2 atau agonis reseptor GLP-1 untuk "
        "diabetes/penurunan risiko kardiovaskular, dan rujuk ke program rehabilitasi jantung. "
        "Perhatian keamanan utama: beberapa obat yang sedang digunakan pasien (metoprolol, "
        "klopidogrel, prasugrel, nitrogliserin semprot) ditandai perlu ditinjau indikasinya "
        "atau membawa risiko bahaya tertentu."),
}


# ── Suntingan penulis ─────────────────────────────────────────────────────────────────
# TERJEMAHAN di atas setia pada keluaran sistem. Penulis kemudian menyunting sebagian
# kesimpulan secara sengaja sebelum lembar dikirim (26 September 2026). Suntingan itu
# dicatat di sini sebagai lapisan tersendiri -- bukan dengan mengubah TERJEMAHAN -- agar
# jejaknya utuh: keluaran sistem (Inggris) -> terjemahan setia -> teks yang dilihat penilai.
# Bab III perlu melaporkan bahwa penilai menilai teks yang telah disunting ini.
#
# Setiap suntingan berupa (penggalan lama, penggalan baru) dan WAJIB ditemukan tepat satu
# kali pada terjemahannya; penggalan yang tidak ditemukan menggagalkan pemeriksaan, bukan
# dilewati diam-diam.
#
#   pasien 1        : suntingan tangan penulis pada lembar R1 (26 dan 27 September)
#   pasien 2        : suntingan tangan penulis pada lembar R1 (27 September)
#   07f42172, 20713969, 227e76d8, 6595b70f
#                   : suntingan tangan penulis pada lembar R1 (27 September) -- nomor 4, 7,
#                     8, dan 12 pada lembar 20 pasien
#   yang lain       : dua pola dari pasien 1 yang diminta diterapkan pula pada pasien lain --
#                     kutipan rekomendasi dalam kurung siku dan frasa "yang sudah tegak"
#
# Istilah tampilan (label_rekomendasi.ISTILAH: "beta blocker", "CKD") diterapkan SESUDAH
# suntingan ini, sehingga penggalan di bawah selalu ditulis menurut terjemahan setia --
# penggantian PGK -> CKD pada pasien 1 dan 2, misalnya, sudah tercakup oleh istilah itu.
SUNTINGAN = {
    "01dc6d0f": [(" yang sudah tegak", ""),
                 (" [CR:1:1, COR1]", ""),
                 (", keduanya ditandai untuk populasi ini", ""),
                 ("Periksa tanda di bawah", "Periksa kelompok cek/stop di bawah")],
    "0333a5c9": [("obesitas berat", "severe obesity")],
    "07f42172": [("dengan penyulit hipertensi", "dengan komplikasi berupa hipertensi")],
    "20713969": [("nefropati diabetik", "diabetic nephropathy"),
                 (" (COR1)", ""),
                 (", COR1)", ")")],
    "227e76d8": [(" pada populasi ini", "")],
    "6595b70f": [("obesitas berat", "severe obesity")],
    # kutipan dalam kurung siku
    "03b03863": [(" [CCD-2023:CR:1:1, COR 1]", "")],
    "3756b42c": [(" [CCD-2023:CR:1:1, COR 1]", "")],
    "d8d734c3": [(" [CCD-2023:CR:1:1, COR 1]", "")],
    # "yang sudah tegak"
    "093d7bf0": [(" yang sudah tegak", "")],
    "75409e1a": [(" yang sudah tegak", "")],
    "e15faae0": [(" yang sudah tegak", "")],
}


def terjemahan(pid):
    """Pengenal pasien lengkap atau delapan karakter -> teks Indonesia, atau None."""
    return TERJEMAHAN.get(pid[:8])


def teks_akhir(pid, dengan_istilah=True):
    """Teks yang dilihat penilai: terjemahan setia, suntingan penulis, lalu istilah tampilan.

    dengan_istilah=False mengembalikan bentuk sebelum istilah tampilan diterapkan; bentuk
    itu dipakai untuk mengenali lembar yang disunting sebelum istilah tersebut ditetapkan.
    ValueError bila sebuah penggalan suntingan tidak ditemukan tepat satu kali.
    """
    from label_rekomendasi import istilah
    t = TERJEMAHAN.get(pid[:8])
    if t is None:
        return None
    for lama, baru in SUNTINGAN.get(pid[:8], ()):
        n = t.count(lama)
        if n != 1:
            raise ValueError("%s: penggalan %r ditemukan %d kali, bukan 1" % (pid[:8], lama, n))
        t = t.replace(lama, baru)
    return istilah(t) if dengan_istilah else t
