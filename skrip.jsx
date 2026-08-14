#target illustrator

var doc = app.activeDocument;

if (doc.selection.length == 0 || doc.selection[0].typename != "TextFrame") {
    alert("Pilih objek teks terlebih dahulu.");
    exit();
}

var textFrame = doc.selection[0];

var folder = Folder.selectDialog("Pilih folder penyimpanan PNG");

if (folder == null) {
    exit();
}

var options = new ExportOptionsPNG24();
options.antiAliasing = true;
options.transparency = true;
options.artBoardClipping = true;
options.matte = false;
options.horizontalScale = 300;
options.verticalScale = 300;

for (var i = 1; i <= 20; i++) {

    var numStr = ("0" + i).slice(-2);

    // Ubah isi teks
    textFrame.contents = numStr;

    app.redraw();

    var file = new File(folder.fsName + "/Angka_" + numStr + ".png");

    doc.exportFile(file, ExportType.PNG24, options);
}

alert("Selesai! Semua PNG berhasil diekspor.");