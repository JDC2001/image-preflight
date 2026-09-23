import tempfile
import unittest
from pathlib import Path

from PIL import Image

from image_validator import ROOT, inspect_image


class ValidatorTests(unittest.TestCase):
    def test_inputs(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as folder:
            root = Path(folder)
            for fmt, ext in [("PNG", "png"), ("JPEG", "jpg"), ("WEBP", "webp")]:
                path = root / f"rgb.{ext}"
                Image.new("RGB", (64, 64), "red").save(path, fmt)
                self.assertEqual(inspect_image(path)["status"], "PASS")
                self.assertEqual(inspect_image(path, max_pixels=100)["status"], "REJECT")
                self.assertEqual(inspect_image(path, max_mb=0.000001)["status"], "REJECT")
            wrong = root / "fake.jpg"
            Image.new("RGB", (10, 10)).save(wrong, "PNG")
            self.assertEqual(inspect_image(wrong)["status"], "CONVERT")
            alpha = root / "alpha.png"
            Image.new("RGBA", (10, 10)).save(alpha)
            self.assertEqual(inspect_image(alpha)["status"], "CONVERT")
            broken = root / "broken.jpg"
            broken.write_bytes(b"not an image")
            self.assertEqual(inspect_image(broken)["status"], "REJECT")
            truncated = root / "truncated.jpg"
            truncated.write_bytes((root / "rgb.jpg").read_bytes()[:-20])
            self.assertEqual(inspect_image(truncated)["status"], "REJECT")
            multi = root / "multi.png"
            Image.new("RGB", (10, 10), "red").save(
                multi, save_all=True, append_images=[Image.new("RGB", (10, 10), "blue")])
            self.assertEqual(inspect_image(multi)["frames"], 2)
            self.assertEqual(inspect_image(multi)["status"], "CONVERT")


if __name__ == "__main__":
    unittest.main()
