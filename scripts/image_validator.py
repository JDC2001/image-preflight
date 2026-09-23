"""Local image preflight. Requires Pillow; run without arguments for the GUI."""

import argparse
import json
import warnings
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
ALLOWED = {"PNG", "JPEG", "WEBP"}
EXTENSIONS = {"PNG": {".png"}, "JPEG": {".jpg", ".jpeg"}, "WEBP": {".webp"}}
DEFAULT_MB = 20
DEFAULT_PIXELS = 40_000_000


def inspect_image(path, max_mb=DEFAULT_MB, max_pixels=DEFAULT_PIXELS):
    path = Path(path).resolve()
    report = {"path": str(path), "status": "REJECT", "issues": [], "notes": []}
    try:
        if max_mb <= 0 or max_pixels <= 0:
            raise ValueError("Limits must be positive")
        size = path.stat().st_size
        report["bytes"] = size
        if not size or size > max_mb * 1024 * 1024:
            raise ValueError("Empty file or file-size limit exceeded")
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(path) as im:
                frames = getattr(im, "n_frames", 1)
                report.update(format=im.format, mode=im.mode, width=im.width,
                              height=im.height, frames=frames)
                if im.width * im.height > max_pixels:
                    raise ValueError("Pixel limit exceeded")
                im.verify()
            # verify() does not fully decode JPEG pixel data.
            with Image.open(path) as im:
                total_pixels = 0
                for frame in range(frames):
                    im.seek(frame)
                    total_pixels += im.width * im.height
                    if total_pixels > max_pixels:
                        raise ValueError("Total frame pixel limit exceeded")
                    im.load()
        fmt = report["format"]
        issues = report["issues"]
        if fmt not in ALLOWED:
            issues.append(f"实际格式 {fmt} 不在 PNG / JPEG / WebP 白名单内")
        if frames != 1:
            issues.append(f"包含 {frames} 帧，本工具按单帧输入策略检查")
        if report["mode"] != "RGB":
            issues.append(f"颜色模式为 {report['mode']}，本工具采用保守的 RGB 策略")
        if fmt in ALLOWED and path.suffix.lower() not in EXTENSIONS[fmt]:
            issues.append("扩展名与实际编码不一致")
        if frames > 1:
            report["notes"].append("转换只保留第一帧，可能丢失动画、其他视图或 HDR 增益信息")
        report["status"] = "CONVERT" if issues else "PASS"
    except Exception as exc:
        report["issues"].append(f"文件无法安全通过校验：{exc}")
    return report


def convert_image(path, max_mb=DEFAULT_MB, max_pixels=DEFAULT_PIXELS):
    report = inspect_image(path, max_mb, max_pixels)
    if report["status"] == "REJECT":
        raise ValueError("；".join(report["issues"]))
    with Image.open(path) as im:
        im.seek(0)
        oriented = ImageOps.exif_transpose(im)
        rgba = oriented.convert("RGBA")
        rgb = Image.new("RGB", rgba.size, "white")
        rgb.paste(rgba, mask=rgba.getchannel("A"))
        # Fresh pixels intentionally exclude source EXIF, MPF, XMP and profiles.
        from uuid import uuid4
        target = ROOT / "converted" / f"{Path(path).stem}_{uuid4().hex[:12]}.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as output:
            rgb.save(output, format="PNG")
    result = inspect_image(target, max_mb, max_pixels)
    result["notes"].append("透明区域合成白底；不保留原始元数据和 HDR，颜色外观需人工核对")
    return result


def describe(report):
    labels = {"PASS": "通过本地校验", "CONVERT": "需要标准化", "REJECT": "拒绝 / 超限或无法解码"}
    lines = [f"文件：{report['path']}", f"结果：{labels[report['status']]}"]
    if "format" in report:
        lines.append(f"真实格式：{report['format']}    帧数：{report['frames']}    颜色：{report['mode']}")
        lines.append(f"尺寸：{report['width']} × {report['height']}")
    if "bytes" in report:
        lines.append(f"大小：{report['bytes'] / 1024 / 1024:.2f} MB")
    lines.extend(report["issues"])
    lines.extend(report["notes"])
    return "\n".join(lines)


def gui():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    from concurrent.futures import ThreadPoolExecutor

    window = tk.Tk()
    window.title("图片真实格式校验")
    window.geometry("880x620")
    window.minsize(640, 420)
    paths = []
    executor = ThreadPoolExecutor(max_workers=1)
    header = ttk.Frame(window, padding=12)
    header.pack(fill="x")
    mb = tk.StringVar(value=str(DEFAULT_MB))
    mp = tk.StringVar(value=str(DEFAULT_PIXELS // 1_000_000))
    ttk.Label(header, text="文件上限 MB").grid(row=0, column=0, padx=4)
    ttk.Entry(header, textvariable=mb, width=7).grid(row=0, column=1)
    ttk.Label(header, text="总像素上限 百万").grid(row=0, column=2, padx=4)
    ttk.Entry(header, textvariable=mp, width=7).grid(row=0, column=3)
    ttk.Label(window, text="本地保守策略，默认上限并非 MiniMax 官方限额；校验不包含内容安全审核。", wraplength=620).pack(padx=12, anchor="w")
    toolbar = ttk.Frame(window, padding=12)
    toolbar.pack(fill="x")
    text_frame = ttk.Frame(window)
    text_frame.pack(fill="both", expand=True, padx=12, pady=(0, 12))
    text = tk.Text(text_frame, wrap="word", font=("Microsoft YaHei", 10))
    scroll = ttk.Scrollbar(text_frame, command=text.yview)
    text.configure(yscrollcommand=scroll.set)
    scroll.pack(side="right", fill="y")
    text.pack(fill="both", expand=True)
    buttons = []

    def start(convert=False):
        if not paths:
            return
        try:
            limits = float(mb.get()), int(float(mp.get()) * 1_000_000)
            if min(limits) <= 0:
                raise ValueError()
        except ValueError:
            messagebox.showerror("输入错误", "上限必须是正数")
            return
        if convert and not messagebox.askyesno("转换副本", "只保留第一帧，透明区域合成白底，移除元数据和 HDR。原图不变。继续？"):
            return
        for button in buttons:
            button.configure(state="disabled")
        text.delete("1.0", "end")
        text.insert("end", "正在本地处理…\n")
        selected = tuple(paths)

        def work():
            results = []
            for path in selected:
                try:
                    result = (convert_image if convert else inspect_image)(path, *limits)
                    results.append(describe(result))
                except Exception as exc:
                    results.append(f"{path}\n处理失败：{exc}")
            return "\n\n".join(results)

        future = executor.submit(work)

        def poll():
            if not future.done():
                window.after(100, poll)
                return
            text.delete("1.0", "end")
            text.insert("end", future.result())
            for button in buttons:
                button.configure(state="normal")
        window.after(100, poll)

    def choose():
        selected = filedialog.askopenfilenames(title="选择图片，可多选", filetypes=[("所有文件", "*.*")])
        if selected:
            paths[:] = selected
            start()

    for label, command in [("选择图片并校验", choose), ("重新校验", start),
                           ("转换为 PNG 副本", lambda: start(True))]:
        button = ttk.Button(toolbar, text=label, command=command)
        button.pack(side="left", padx=(0, 8))
        buttons.append(button)
    window.mainloop()
    executor.shutdown(wait=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="*")
    parser.add_argument("--convert", action="store_true")
    parser.add_argument("--max-mb", type=float, default=DEFAULT_MB)
    parser.add_argument("--max-pixels", type=int, default=DEFAULT_PIXELS)
    args = parser.parse_args()
    if not args.files:
        gui()
    else:
        results = []
        for file in args.files:
            try:
                results.append((convert_image if args.convert else inspect_image)(file, args.max_mb, args.max_pixels))
            except Exception as exc:
                results.append({"path": file, "status": "REJECT", "issues": [str(exc)]})
        print(json.dumps(results, ensure_ascii=False, indent=2))
        raise SystemExit(0 if all(r["status"] == "PASS" for r in results) else 1)
