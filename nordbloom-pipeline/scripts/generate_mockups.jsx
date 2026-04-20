// Nordbloom mockup generator — ExtendScript for Adobe Photoshop.
//
// Reads a batch descriptor JSON from ~/nordbloom_pipeline/working/current_batch.json
// with shape:
//   {
//     "results_path": "/abs/path/to/results.json",
//     "tasks": [
//       {"psd": "...", "poster": "...", "output": "...", "poster_name": "...", "mockup_name": "..."},
//       ...
//     ]
//   }
//
// For each task:
//   1. Opens the PSD.
//   2. Walks all layers (recursively into groups) and picks the largest visible
//      smart-object layer by bounds-area. Name-agnostic.
//   3. Enters the smart object's contents, replaces everything with the poster
//      (center-cropped to the smart object's aspect ratio — no white edges),
//      saves the smart object (SAVECHANGES).
//   4. Exports the parent document as JPEG, saveAs copy = true, quality ~95.
//   5. Closes parent with DONOTSAVECHANGES and purges caches.
//
// Writes results incrementally so Python sees progress even on crash.

#target photoshop

(function main() {
    app.displayDialogs = DialogModes.NO;

    var batchFile = findBatchFile();
    if (!batchFile) {
        writeError("Batch file not found at ~/nordbloom_pipeline/working/current_batch.json");
        return;
    }

    var batchJson;
    try {
        batchJson = readTextFile(batchFile);
    } catch (e) {
        writeError("Could not read batch file: " + e);
        return;
    }

    var batch;
    try {
        batch = JSON.parse(batchJson);
    } catch (e) {
        writeError("Invalid batch JSON: " + e);
        return;
    }

    var tasks = batch.tasks || [];
    var resultsPath = batch.results_path;

    var results = [];
    for (var i = 0; i < tasks.length; i++) {
        var task = tasks[i];
        var startMs = new Date().getTime();
        var res = {
            task: task,
            status: "ok",
            error: "",
            elapsed_ms: 0,
            so_width: 0,
            so_height: 0
        };

        try {
            var info = processMockup(task);
            res.so_width = info.so_width;
            res.so_height = info.so_height;
        } catch (e) {
            res.status = "failed";
            res.error = String(e) + (e.line ? " (line " + e.line + ")" : "");
            cleanupOpenDocs();
        }

        res.elapsed_ms = new Date().getTime() - startMs;
        results.push(res);

        try { app.purge(PurgeTarget.ALLCACHES); } catch (ignore) {}

        // Flush results incrementally so a crash doesn't lose progress.
        try { writeResults(resultsPath, results); } catch (ignore) {}
    }

    try { writeResults(resultsPath, results); } catch (ignore) {}
})();


// ---------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------

function findBatchFile() {
    var home = $.getenv("HOME");
    var path = home + "/nordbloom_pipeline/working/current_batch.json";
    var f = new File(path);
    return f.exists ? f : null;
}

function readTextFile(file) {
    file.encoding = "UTF-8";
    file.open("r");
    var content = file.read();
    file.close();
    return content;
}

function writeResults(path, results) {
    var f = new File(path);
    f.encoding = "UTF-8";
    f.open("w");
    f.write(JSON.stringify(results));
    f.close();
}

function writeError(msg) {
    var home = $.getenv("HOME");
    var f = new File(home + "/nordbloom_pipeline/working/jsx_error.log");
    f.encoding = "UTF-8";
    f.open("a");
    f.writeln(new Date().toString() + "  " + msg);
    f.close();
}

function cleanupOpenDocs() {
    var guard = 0;
    while (app.documents.length > 0 && guard < 20) {
        try {
            app.activeDocument.close(SaveOptions.DONOTSAVECHANGES);
        } catch (e) {
            break;
        }
        guard++;
    }
}

// ---------------------------------------------------------------------
// Core processing
// ---------------------------------------------------------------------

function processMockup(task) {
    var psdFile = new File(task.psd);
    var posterFile = new File(task.poster);
    var outFile = new File(task.output);

    if (!psdFile.exists) throw new Error("PSD not found: " + task.psd);
    if (!posterFile.exists) throw new Error("Poster not found: " + task.poster);

    var outDir = outFile.parent;
    if (!outDir.exists) outDir.create();

    var doc = app.open(psdFile);

    var soLayer = findLargestSmartObject(doc);
    if (!soLayer) {
        doc.close(SaveOptions.DONOTSAVECHANGES);
        throw new Error("No smart-object layer found");
    }

    doc.activeLayer = soLayer;

    // Enter the smart object contents
    var idPlcCntnt = stringIDToTypeID("placedLayerEditContents");
    try {
        executeAction(idPlcCntnt, new ActionDescriptor(), DialogModes.NO);
    } catch (e) {
        doc.close(SaveOptions.DONOTSAVECHANGES);
        throw new Error("placedLayerEditContents failed: " + e);
    }

    var soDoc = app.activeDocument;
    var soW = Math.round(soDoc.width.as("px"));
    var soH = Math.round(soDoc.height.as("px"));
    var soMode = soDoc.mode;

    // Open poster in a temp doc we can mutate freely (crop / resize / mode).
    var posterDoc = app.open(posterFile);

    try {
        if (posterDoc.mode !== soMode) {
            if (soMode === DocumentMode.CMYK) {
                posterDoc.changeMode(ChangeMode.CMYK);
            } else if (soMode === DocumentMode.RGB) {
                posterDoc.changeMode(ChangeMode.RGB);
            } else if (soMode === DocumentMode.GRAYSCALE) {
                posterDoc.changeMode(ChangeMode.GRAYSCALE);
            }
        }
    } catch (e) { /* non-fatal; continue */ }

    centerCropToRatio(posterDoc, soW / soH);

    // Resize to exactly match the smart object canvas dimensions.
    posterDoc.resizeImage(
        UnitValue(soW, "px"),
        UnitValue(soH, "px"),
        posterDoc.resolution,
        ResampleMethod.BICUBIC
    );

    posterDoc.selection.selectAll();
    posterDoc.selection.copy();
    posterDoc.close(SaveOptions.DONOTSAVECHANGES);

    // Back to the smart object document.
    app.activeDocument = soDoc;

    // Unlock any background layers and clear out existing content so we
    // end up with a single layer = the pasted poster after flatten.
    unlockBackgroundLayers(soDoc);

    // Remove all layers except the last so paste has room (paste adds a new layer).
    var guard = 0;
    while (soDoc.layers.length > 1 && guard < 500) {
        try {
            soDoc.layers[soDoc.layers.length - 1].remove();
        } catch (e) { break; }
        guard++;
    }

    // Select all and clear the remaining layer so the paste replaces everything.
    try {
        soDoc.selection.selectAll();
        soDoc.selection.clear();
        soDoc.selection.deselect();
    } catch (e) { /* empty selection etc — fine */ }

    soDoc.paste();
    soDoc.flatten();

    // Save smart object — this is what actually propagates the change into the
    // parent PSD (in memory only; parent is closed WITHOUT saving below).
    soDoc.close(SaveOptions.SAVECHANGES);

    // Export the parent as JPEG at its native resolution.
    var jpegOpts = new JPEGSaveOptions();
    jpegOpts.quality = 10;                       // 0-12 scale, ~quality 95
    jpegOpts.embedColorProfile = true;
    jpegOpts.formatOptions = FormatOptions.STANDARDBASELINE;
    jpegOpts.matte = MatteType.NONE;

    doc.saveAs(outFile, jpegOpts, true, Extension.LOWERCASE);
    doc.close(SaveOptions.DONOTSAVECHANGES);

    return { so_width: soW, so_height: soH };
}

function centerCropToRatio(docRef, targetRatio) {
    var w = docRef.width.as("px");
    var h = docRef.height.as("px");
    var cur = w / h;
    if (Math.abs(cur - targetRatio) < 0.001) return;

    var left, top, right, bottom;
    if (cur > targetRatio) {
        // Wider than target — crop the sides.
        var newW = h * targetRatio;
        var xOff = (w - newW) / 2;
        left = xOff;
        top = 0;
        right = xOff + newW;
        bottom = h;
    } else {
        // Taller than target — crop top/bottom.
        var newH = w / targetRatio;
        var yOff = (h - newH) / 2;
        left = 0;
        top = yOff;
        right = w;
        bottom = yOff + newH;
    }
    docRef.crop([
        UnitValue(left, "px"),
        UnitValue(top, "px"),
        UnitValue(right, "px"),
        UnitValue(bottom, "px")
    ]);
}

function unlockBackgroundLayers(docRef) {
    for (var i = 0; i < docRef.artLayers.length; i++) {
        try {
            if (docRef.artLayers[i].isBackgroundLayer) {
                docRef.artLayers[i].isBackgroundLayer = false;
            }
        } catch (e) { /* ignore */ }
    }
}

function findLargestSmartObject(doc) {
    var best = null;
    var bestArea = -1;

    function areaOf(layer) {
        try {
            var b = layer.bounds;
            var lw = b[2].as("px") - b[0].as("px");
            var lh = b[3].as("px") - b[1].as("px");
            return lw * lh;
        } catch (e) { return 0; }
    }

    function walk(layers, onlyVisible) {
        for (var i = 0; i < layers.length; i++) {
            var l = layers[i];
            if (l.typename === "LayerSet") {
                if (onlyVisible && !l.visible) continue;
                walk(l.layers, onlyVisible);
                continue;
            }
            if (l.kind === LayerKind.SMARTOBJECT) {
                if (onlyVisible && !l.visible) continue;
                var a = areaOf(l);
                if (a > bestArea) {
                    bestArea = a;
                    best = l;
                }
            }
        }
    }

    // Prefer visible smart objects; fall back to any smart object.
    walk(doc.layers, true);
    if (!best) walk(doc.layers, false);
    return best;
}
