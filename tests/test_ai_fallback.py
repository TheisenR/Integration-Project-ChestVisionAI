import unittest
import numpy as np
import app


class FallbackGradcamTests(unittest.TestCase):
    def test_fallback_gradcam_png_works_without_opencv(self):
        original_cv2 = app.cv2
        app.cv2 = None
        try:
            img_uint8 = np.zeros((16, 16, 3), dtype=np.uint8)
            png_bytes = app.create_fallback_gradcam_png(img_uint8)
        finally:
            app.cv2 = original_cv2

        self.assertTrue(png_bytes.startswith(b"\x89PNG\r\n\x1a\n"))

    def test_predict2_returns_fallback_png_without_opencv(self):
        original_cv2 = app.cv2
        app.cv2 = None
        try:
            img_bytes = b"\x89PNG\r\n\x1a\n"  # placeholder bytes; preprocessing will fall back to zeros
            result = app.predict2(img_bytes)
        finally:
            app.cv2 = original_cv2

        self.assertIn("gradcam_png", result)
        self.assertTrue(result["gradcam_png"].startswith(b"\x89PNG\r\n\x1a\n"))


if __name__ == "__main__":
    unittest.main()
