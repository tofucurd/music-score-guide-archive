"""Render the fourth-movement master from the frozen clock and percussion events."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import soundfile as sf

from percussion import remix_signal

PROJECT = Path(__file__).resolve().parents[1]
DATA = PROJECT / "data"
BLOCK = 131072


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def pcm_hash(path, kind, dtype):
    digest = hashlib.new(kind)
    for block in sf.blocks(path, blocksize=BLOCK, dtype=dtype, always_2d=True):
        digest.update(block.astype(block.dtype.newbyteorder("<"), copy=False))
    return digest.hexdigest()


def verify_source(path, spec):
    info = sf.info(path)
    if (info.samplerate, info.channels, info.frames, info.subtype) != (
        spec["sample_rate"], spec["channels"], spec["frames"], "PCM_16"
    ):
        raise ValueError(f"Incorrect audio format or length for {path.name}")
    file_sha = sha256(path)
    if file_sha != spec["sha256"] and pcm_hash(path, "md5", "int16") != spec["pcm_md5"]:
        raise ValueError(f"Different recording or mastering in {path.name}")
    return file_sha


def crop_donor(source, dest, frames, fade_tail_s):
    # Replicate the 16-bit production crop before converting it to float.
    with sf.SoundFile(source) as src, sf.SoundFile(
        dest, "w", src.samplerate, src.channels, format="FLAC", subtype=src.subtype
    ) as out:
        fade = round(src.samplerate * fade_tail_s)
        for start in range(0, frames, BLOCK):
            block = src.read(min(BLOCK, frames - start), dtype="float32", always_2d=True)
            position = np.arange(start, start + len(block))
            gain = np.clip((frames - 1 - position) / fade, 0, 1)
            block *= np.sin(gain * np.pi / 2)[:, None] ** 2
            out.write(block)


def stretch(source, dest, scratch, config):
    rate = config["sample_rate"]
    samples = config["frames"]
    raw = scratch / "source.wav"
    stretched = scratch / "stretched.wav"
    source_frames = sf.info(source).frames
    with sf.SoundFile(raw, "w", rate, 2, subtype="FLOAT") as out:
        for block in sf.blocks(source, blocksize=BLOCK, dtype="float32"):
            out.write(block * .5)

    subprocess.run([
        "rubberband", "-q", "-3", "--ignore-clipping", "--centre-focus",
        "-t", str(samples / source_frames),
        "-M", str(DATA / "engine-keyframes.txt"), str(raw), str(stretched),
    ], check=True)
    info = sf.info(stretched)
    if info.samplerate != rate or info.channels != 2 or abs(info.frames - samples) >= .1 * rate:
        raise ValueError(f"Unexpected format or length from Rubber Band: {info}")
    peak = max(np.max(abs(block)) for block in sf.blocks(stretched, blocksize=BLOCK, dtype="float32"))
    gain = min(2., .998 / max(.001, peak))
    with sf.SoundFile(dest, "w", rate, 2, subtype="PCM_24") as out:
        for block in sf.blocks(stretched, blocksize=BLOCK, frames=min(info.frames, samples), dtype="float32"):
            out.write(block * gain)
        if info.frames < samples:
            out.write(np.zeros((samples - info.frames, 2), dtype="float32"))
    return info.frames, float(gain * .5)


def percussion_events(path, config):
    with path.open(encoding="utf-8", newline="") as stream:
        rows = []
        for row in csv.DictReader(stream):
            event = {key: float(row[key]) for key in ("attack", "stop", "decay", "gain")}
            event.update(inst=row["inst"], roll={"True": True, "False": False}[row["roll"]],
                         pitch=float(row["pitch"]) if row["pitch"] else None)
            rows.append(event)
    if len(rows) != sum(config["accepted_by_part"].values()):
        raise ValueError("Incomplete percussion controls")
    return rows


def prepare(sources, directory):
    manifest = read_json(PROJECT / "sources.json")
    source_by_role = {item["role"]: item for item in manifest["external_files"]}
    verified = {}
    for spec in source_by_role.values():
        path = sources / spec["path"]
        if path.exists() or spec["required_for_render"]:
            verified[spec["role"]] = verify_source(path, spec)

    dry = read_json(DATA / "dry.json")
    wet = read_json(DATA / "percussion.json")
    events = DATA / "percussion-events.csv"
    for path, expected in ((DATA / "command.csv", dry["clock_sha256"]),
                           (DATA / "engine-keyframes.txt", dry["engine_keyframes_sha256"]),
                           (events, wet["events_sha256"])):
        if sha256(path) != expected:
            raise ValueError(f"Changed release control file: {path.name}")
    engine_version = subprocess.check_output(
        ["rubberband", "--version"], text=True, stderr=subprocess.STDOUT
    ).strip()
    donor = source_by_role["donor"]
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=directory) as tmp:
        scratch = Path(tmp)
        crop = scratch / "music.flac"
        dry_audio = scratch / "dry.flac"
        master = scratch / "transplant.flac"
        crop_donor(sources / donor["path"], crop, dry["donor_music_frames"], dry["donor_fade_tail_s"])
        if pcm_hash(crop, "md5", "int16") != dry["source_stream_md5"]:
            raise ValueError("Cropped donor samples differ from the approved input")
        engine_frames, net_gain = stretch(crop, dry_audio, scratch, dry)
        remix_signal(dry_audio, percussion_events(events, wet), master)
        digest = sha256(master)
        decoded = pcm_hash(master, "sha256", "int32")
        receipt = {
            "label": wet["label"], "sha256": digest, "expected_sha256": wet["output_sha256"],
            "pcm_s32le_sha256": decoded, "matches_release_pcm": decoded == wet["pcm_s32le_sha256"],
            "samplerate": sf.info(master).samplerate, "frames": sf.info(master).frames,
            "channels": sf.info(master).channels, "subtype": sf.info(master).subtype,
            "engine": dry["engine"], "engine_version": engine_version, "passes": dry["passes"],
            "native_engine_frames": engine_frames, "net_gain": net_gain,
            "clock_sha256": dry["clock_sha256"], "engine_keyframes_sha256": dry["engine_keyframes_sha256"],
            "source_sha256": donor["sha256"], "input_sha256": verified,
            "dry_sha256": sha256(dry_audio), "percussion_events_sha256": wet["events_sha256"],
        }
        receipt_path = scratch / "receipt.json"
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        master.replace(directory / master.name)
        receipt_path.replace(directory / receipt_path.name)
    print(json.dumps(receipt, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    prepare(args.sources, args.out)
