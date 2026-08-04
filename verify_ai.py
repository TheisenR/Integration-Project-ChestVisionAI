import io
from PIL import Image
import app as app_module

img = Image.new('RGB', (224, 224), color=(255, 255, 255))
buf = io.BytesIO()
img.save(buf, format='PNG')
raw = buf.getvalue()
result = app_module.predict2(raw)
print(result['label'])
print(result['prob'])
print(len(result['probs']))
print(bool(result['gradcam_png']))
print(type(result['gradcam_png']).__name__)
print(len(result['gradcam_png']))
