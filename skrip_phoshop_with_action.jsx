#target photoshop

function runBatchActionFixed() {
    var inputFolder = Folder.selectDialog("Pilih folder berisi 100 foto asli:");
    if (!inputFolder) return;

    var outputFolder = Folder.selectDialog("Pilih folder untuk menyimpan hasil:");
    if (!outputFolder) return;

    var fileList = inputFolder.getFiles(/\.(jpg|jpeg|png|tif|psd)$/i);
    if (fileList.length === 0) {
        alert("Tidak ada gambar ditemukan di folder input!");
        return;
    }

    var actionName = "pass_foto_smk";
    var actionSet  = "Default Actions";

    for (var i = 0; i < fileList.length; i++) {
        var doc = open(fileList[i]);

        // 1. PAKSA CONVERT BACKGROUND MENJADI LAYER 0 (MENGGUNAKAN ACTION DESCRIPTOR)
        try {
            if (doc.activeLayer.isBackgroundLayer) {
                var idset = charIDToTypeID("setd");
                var desc = new ActionDescriptor();
                var idnull = charIDToTypeID("null");
                var ref = new ActionReference();
                ref.putProperty(charIDToTypeID("Lyr "), charIDToTypeID("Bckg"));
                desc.putReference(idnull, ref);
                var idto = charIDToTypeID("to  ");
                var descLayer = new ActionDescriptor();
                descLayer.putString(charIDToTypeID("Nm  "), "Layer 0");
                desc.putObject(idto, charIDToTypeID("Lyr "), descLayer);
                executeAction(idset, desc, DialogModes.NO);
            }
        } catch (e) {
            // Abaikan jika sudah berbentuk layer biasa
        }

        // 2. JALANKAN ACTION "pass_foto"
        try {
            app.doAction(actionName, actionSet);
        } catch (e) {
            alert("Gagal pada foto: " + doc.name + "\nDetail Error: " + e.message);
            doc.close(SaveOptions.DONOTSAVECHANGES);
            return;
        }

        // 3. PROSES PENYIMPANAN OTOMATIS (MENGATASI KENDALA GAMBAR TIDAK TERSIMPAN)
        var saveFile = new File(outputFolder + "/" + doc.name);
        var jpegOptions = new JPEGSaveOptions();
        jpegOptions.quality = 11; // Kualitas JPEG (1-12)
        
        // Flatten image jika ada multiple layers sebelum save
        doc.flatten();
        
        // Simpan file
        doc.saveAs(saveFile, jpegOptions, true, Extension.LOWERCASE);
        
        // Tutup dokumen
        doc.close(SaveOptions.DONOTSAVECHANGES);
    }

    alert("Selesai! 100 foto berhasil diubah ke Layer 0, diproses, dan disimpan.");
}

runBatchActionFixed();
