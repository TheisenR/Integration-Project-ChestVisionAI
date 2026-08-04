import numpy as np
import app

print('load_ai_model', app.load_ai_model())
img = np.zeros((224, 224, 3), dtype=np.uint8)
img_array = np.expand_dims(img, axis=0)
heatmap, preds = app.make_gradcam_heatmap(img_array)
print('heatmap_shape', heatmap.shape)
print('preds_shape', preds.shape)
img_bgr = np.zeros((224, 224, 3), dtype=np.uint8)
png = app.overlay_png(img_bgr)
print('png_bytes', len(png), png[:8])
