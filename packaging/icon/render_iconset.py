import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

HERE = Path(__file__).parent
SVG_PATH = HERE / "spidermapp_icon.svg"
ICONSET_DIR = HERE / "Spidermapp.iconset"

SIZES = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}


def main() -> None:
    app = QApplication(sys.argv)
    renderer = QSvgRenderer(str(SVG_PATH))
    ICONSET_DIR.mkdir(exist_ok=True)

    for filename, size in SIZES.items():
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(0)
        painter = QPainter(img)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(painter)
        painter.end()
        img.save(str(ICONSET_DIR / filename))
        print(f"wrote {filename} ({size}x{size})")


if __name__ == "__main__":
    main()
