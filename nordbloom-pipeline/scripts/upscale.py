"""Upscale one poster using Upscayl CLI (or Real-ESRGAN fallback), convert to JPEG.

Usage:
    from upscale import upscale_poster
    upscale_poster(src_png, dest_jpg, upscayl_bin, models_dir, model_name, scale, quality)
"""
from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path

from PIL import Image


class UpscaleError(RuntimeError):
    pass


def _run_upscayl(
    upscayl_bin: str,
    src_png: Path,
    dest_png: Path,
    models_dir: str | None,
    model_name: str,
    scale: int,
) -> None:
    """Invoke Upscayl CLI, trying both model name variants if needed."""
    # Upscayl CLI and Real-ESRGAN share the same arg style:
    #   -i input -o output -s scale -n model_name [-m models_dir]
    name_variants = [model_name]
    # Try both common spellings automatically.
    alt = (
        "real-esrgan-x4plus"
        if model_name == "realesrgan-x4plus"
        else "realesrgan-x4plus"
    )
    if alt not in name_variants:
        name_variants.append(alt)

    last_err: str = ""
    for name in name_variants:
        cmd = [
            upscayl_bin,
            "-i", str(src_png),
            "-o", str(dest_png),
            "-s", str(scale),
            "-n", name,
        ]
        if models_dir:
            cmd += ["-m", models_dir]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                check=False,
            )
        except FileNotFoundError as e:
            raise UpscaleError(f"Upscayl binary not found: {upscayl_bin}") from e

        if result.returncode == 0 and dest_png.exists():
            return  # success

        last_err = (
            f"cmd={' '.join(cmd)}\n"
            f"rc={result.returncode}\n"
            f"stdout={result.stdout[-500:]}\n"
            f"stderr={result.stderr[-500:]}"
        )
        # Wipe any half-written output before retry.
        if dest_png.exists():
            dest_png.unlink()

    raise UpscaleError(f"Upscayl failed for all model-name variants.\n{last_err}")


def upscale_poster(
    src_png: Path,
    dest_jpg: Path,
    upscayl_bin: str,
    models_dir: str | None,
    model_name: str = "realesrgan-x4plus",
    scale: int = 4,
    jpeg_quality: int = 95,
    working_dir: Path | None = None,
) -> dict:
    """Upscale one PNG, convert to progressive JPEG. Returns metadata dict.

    Idempotent: if dest_jpg already exists, returns immediately with status=skipped.
    """
    src_png = Path(src_png)
    dest_jpg = Path(dest_jpg)

    if dest_jpg.exists():
        return {
            "status": "skipped",
            "reason": "already_exists",
            "src": str(src_png),
            "dest": str(dest_jpg),
        }

    if not src_png.exists():
        raise UpscaleError(f"Source not found: {src_png}")

    working_dir = Path(working_dir) if working_dir else dest_jpg.parent
    working_dir.mkdir(parents=True, exist_ok=True)
    dest_jpg.parent.mkdir(parents=True, exist_ok=True)

    tmp_png = working_dir / f".upscale_tmp_{os.getpid()}_{src_png.stem}.png"
    if tmp_png.exists():
        tmp_png.unlink()

    t0 = time.time()
    try:
        _run_upscayl(upscayl_bin, src_png, tmp_png, models_dir, model_name, scale)
        upscale_seconds = time.time() - t0

        t1 = time.time()
        with Image.open(tmp_png) as im:
            if im.mode != "RGB":
                im = im.convert("RGB")
            im.save(
                dest_jpg,
                format="JPEG",
                quality=jpeg_quality,
                progressive=True,
                optimize=True,
            )
        jpeg_seconds = time.time() - t1

        src_size_mb = src_png.stat().st_size / (1024 * 1024)
        dest_size_mb = dest_jpg.stat().st_size / (1024 * 1024)

        return {
            "status": "ok",
            "src": str(src_png),
            "dest": str(dest_jpg),
            "upscale_seconds": round(upscale_seconds, 2),
            "jpeg_seconds": round(jpeg_seconds, 2),
            "src_size_mb": round(src_size_mb, 2),
            "dest_size_mb": round(dest_size_mb, 2),
        }
    finally:
        if tmp_png.exists():
            try:
                tmp_png.unlink()
            except OSError:
                pass


def upscale_all(
    posters_dir: Path,
    output_dir: Path,
    working_dir: Path,
    upscayl_bin: str,
    models_dir: str | None,
    model_name: str,
    scale: int,
    jpeg_quality: int,
    logger,
    skip_names: set[str] | None = None,
) -> list[dict]:
    """Upscale every PNG in posters_dir. Returns list of result dicts.

    skip_names: set of poster stem names (without extension) to skip entirely —
    useful when the poster is already marked completed in state.
    """
    skip_names = skip_names or set()
    posters_dir = Path(posters_dir)
    output_dir = Path(output_dir)

    pngs = sorted(
        p for p in posters_dir.iterdir()
        if p.is_file() and p.suffix.lower() == ".png"
    )

    results = []
    for png in pngs:
        if png.stem in skip_names:
            logger.info(f"[upscale] {png.stem}: skip (already completed in state)")
            continue

        dest = output_dir / f"{png.stem}.jpg"
        logger.info(f"[upscale] {png.stem}: starting …")
        try:
            res = upscale_poster(
                src_png=png,
                dest_jpg=dest,
                upscayl_bin=upscayl_bin,
                models_dir=models_dir,
                model_name=model_name,
                scale=scale,
                jpeg_quality=jpeg_quality,
                working_dir=working_dir,
            )
            if res["status"] == "skipped":
                logger.info(f"[upscale] {png.stem}: already exists, skipping upscale")
            else:
                logger.info(
                    f"[upscale] {png.stem}: OK "
                    f"(upscale {res['upscale_seconds']}s, "
                    f"jpeg {res['jpeg_seconds']}s, "
                    f"{res['src_size_mb']} MB -> {res['dest_size_mb']} MB)"
                )
            results.append(res)
        except Exception as e:
            logger.error(f"[upscale] {png.stem}: FAILED: {e}")
            results.append({
                "status": "failed",
                "src": str(png),
                "error": str(e),
            })
    return results
