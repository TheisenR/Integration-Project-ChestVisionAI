import unittest
import numpy as np
import app


class GradcamFallbackTests(unittest.TestCase):
    def test_fallback_overlay_png_returns_png_bytes(self):
        img = np.zeros((64, 64, 3), dtype=np.uint8)
        png = app.create_fallback_gradcam_png(img)
        self.assertIsInstance(png, bytes)
        self.assertTrue(png.startswith(b'\x89PNG'))


if __name__ == '__main__':
    unittest.main()
