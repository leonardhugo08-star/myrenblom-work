# Nordbloom Gallery — Photoshop Mockup Pipeline

Batch pipeline för att upscala posters och generera Etsy-mockups automatiskt.

## Vad den gör

För varje poster i `input/posters/`:
1. **Upscale 4x** via Upscayl CLI (real-esrgan-x4plus) → JPEG kvalitet 95, progressive, sparas i `output/upscaled_for_print/` (för Gelato print-on-demand)
2. **Genererar 10 mockups** via Photoshop ExtendScript. Postern sätts in i det största smart object-lagret i varje PSD. Center-crop till smart objectets ratio. Export som JPEG kvalitet 95 i PSD:ns native upplösning. Sparas i `output/mockups/[poster_namn]/[poster_namn]_[mockup_namn].jpg`

## Körinstruktioner (Mac Mini)

### Första gången

```bash
# 1. Klona/uppdatera repot till valfri plats (t.ex. ~/code/myrenblom-work/)
cd ~/code/myrenblom-work
git checkout claude/photoshop-batch-mockups-Ic6x9
git pull

# 2. Kör setup (EN gång). Detta:
#    - Skapar ~/nordbloom_pipeline/
#    - Flyttar Desktop-filerna dit
#    - Skapar .venv, installerar pillow + psutil
#    - Detekterar Upscayl CLI och Photoshop-version
#    - Skriver config.env med detekterade sökvägar
cd nordbloom-pipeline
./setup.sh
```

Om setup rapporterar att Upscayl CLI inte hittades i `/Applications/Upscayl.app`, installera Real-ESRGAN:
```bash
brew install realesrgan-ncnn-vulkan
# kör ./setup.sh igen
```

### Vid varje körning

```bash
cd ~/code/myrenblom-work/nordbloom-pipeline
./run_pipeline.sh
```

Pipelinen är **idempotent**: den hoppar över posters som redan är klara enligt `~/nordbloom_pipeline/state/completed.json`. Om den kraschar mitt i en batch fortsätter nästa körning från rätt ställe.

### Crash-simulering (verifiering)

```bash
./run_pipeline.sh &
PID=$!
sleep 120   # vänta tills batch 2 är igång
kill -9 $PID
pkill -f "Adobe Photoshop"
./run_pipeline.sh  # ska hoppa över klara posters
```

## Mappstruktur på Macen

```
~/nordbloom_pipeline/
├── .venv/                    ← Python venv
├── input/
│   ├── posters/              ← PNG-posters
│   └── mockups/              ← PSD-mockups
├── working/                  ← current_batch.json, temp-PNG från Upscayl
├── output/
│   ├── upscaled_for_print/   ← upscalade JPEGs för Gelato
│   └── mockups/              ← per-poster-mappar med 10 JPEGs
├── logs/                     ← run_YYYYMMDD_HHMMSS.log
└── state/
    └── completed.json        ← resume-state
```

Repot innehåller bara scripten. All data (input/output/logs/state) ligger utanför git.

## Konfiguration

`config.env` (skapas av `setup.sh`) innehåller:

```bash
NORDBLOOM_ROOT="$HOME/nordbloom_pipeline"
UPSCAYL_BIN="/Applications/Upscayl.app/Contents/Resources/bin/upscayl-bin"
UPSCAYL_MODELS_DIR="/Applications/Upscayl.app/Contents/Resources/models"
UPSCAYL_MODEL_NAME="realesrgan-x4plus"
PHOTOSHOP_APP_NAME="Adobe Photoshop 2024"
BATCH_SIZE=3
PS_RESTART_SLEEP=10
MIN_MOCKUPS_OK=8
JPEG_QUALITY=95
```

Redigera valfria fält manuellt vid behov. Om Upscayl CLI inte hittas automatiskt, peka på Real-ESRGAN:
```bash
UPSCAYL_BIN="/opt/homebrew/bin/realesrgan-ncnn-vulkan"
UPSCAYL_MODELS_DIR="/opt/homebrew/share/realesrgan-ncnn-vulkan/models"
```

## Loggning

`~/nordbloom_pipeline/logs/run_YYYYMMDD_HHMMSS.log` innehåller:
- System-info (RAM, disk, CPU)
- Per-poster: upscale-tid, mockup-resultat (N/10 OK)
- Per-batch: peak RAM, Photoshop-restart-markörer
- Per-mockup: tid, eventuella felmeddelanden
- Sammanfattning: total tid, genomsnittlig RAM, peak RAM

Efter första körningen: granska peak RAM. Om under 6 GB kan `BATCH_SIZE` höjas till 5. Om över 7 GB, sänk till 2.

## Felhantering

- **Per-mockup-fel** (t.ex. PSD utan smart object): loggas som `FAILED: poster + mockup: <error>`, pipelinen fortsätter med nästa mockup.
- **Poster klar** när upscale OK + minst 8/10 mockups OK (`MIN_MOCKUPS_OK=8`). Lägre resultat → postern flaggas i loggen och INTE markerad som klar, så du kan re-köra efter fix.
- **Photoshop-krasch**: mockup-steget fångas per batch. Om Photoshop kraschar under JSX, fångas det av Python-wrappern och batchen markeras som delvis misslyckad. Nästa körning retryar kvarvarande kombinationer.

## Filer i detta repo

- `setup.sh` — one-time setup
- `run_pipeline.sh` — thin shell wrapper
- `scripts/pipeline.py` — huvudorchestrator (state, RAM, batching, Photoshop-invocation)
- `scripts/upscale.py` — upscale-modul (Upscayl CLI + Pillow)
- `scripts/generate_mockups.jsx` — Photoshop ExtendScript
- `requirements.txt` — pillow, psutil
- `config.env.example` — mall (den riktiga `config.env` skapas av setup.sh och är git-ignored)
