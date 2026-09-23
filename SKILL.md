---
name: image-preflight
description: Inspect an image's real encoding (not just its extension), frames, mode, size and total pixels before submitting it to an image API, and optionally convert it into a compliant single-frame RGB PNG copy.
---

# Image Preflight

Use this skill whenever an image is about to be uploaded or submitted to a
third-party image API and the user needs confidence in what the file really
is. It catches files whose extension lies (e.g. an MPO mislabeled as .jpg),
multi-frame images, oversized dimensions, and files Pillow cannot fully
decode - before they cause a hard-to-debug API rejection.

## How to run

All commands work from any directory; the script is invoked by full path.

```bash
# Inspect only (read-only, never modifies the original)
python "$HOME/.codex/skills/image-preflight/scripts/image_validator.py" "<image path>"

# Inspect, then convert to a compliant PNG copy when needed
python "$HOME/.codex/skills/image-preflight/scripts/image_validator.py" "<image path>" --convert

# Run the built-in test suite
python -m unittest -v "$HOME/.codex/skills/image-preflight/scripts/test_image_validator.py"
```

Without arguments the script opens a Tkinter GUI (single-frame strategy,
white-background compositing). Prefer the CLI when driving it from a session.

## Reading the result

The report prints one of three statuses:

- `PASS` - format is PNG / JPEG / WebP, single frame, RGB mode, within
  limits, and the extension matches the real encoding.
- `CONVERT` - decodable but one or more conservative rules flagged it
  (multi-frame, non-RGB mode, extension mismatch, ...). Decide whether to
  run `--convert` based on the issues listed.
- `REJECT` - unreadable, empty, or over the size/pixel limits; do not
  submit it.

## Defaults and caveats

- Limits: 20 MB per file, 40 million total pixels across all frames. These
  are conservative local limits, not any third-party API's official cap -
  pass `--max-mb` / `--max-pixels` only if the user asks for different
  numbers.
- `--convert` writes a new file to `converted/` next to the script and
  never modifies the source. The copy keeps only frame 1, flattens
  transparency onto white, and strips EXIF/MPF/XMP/HDR data - the output
  may differ visually from the original (colors, dynamic range), so flag
  that to the user.
- Conversion is intentionally lossy about metadata. Do not use it to
  "sanitize" an image into something the user did not ask for.
- A passing local check says nothing about content safety review; do not
  represent it as such.
- Pillow must be installed (`pip install pillow`) - the script does not
  auto-install it.
