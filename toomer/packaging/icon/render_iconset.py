"""Genera toomer.png, Toomer.iconset/ (→ .icns con iconutil) y Toomer.ico desde toomer_icon.svg."""
import struct
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QImage, QPainter
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QApplication

HERE = Path(__file__).parent
SVG = HERE / "toomer_icon.svg"
ICONSET = HERE / "Toomer.iconset"
SIZES = {"icon_16x16.png": 16, "icon_16x16@2x.png": 32, "icon_32x32.png": 32, "icon_32x32@2x.png": 64,
         "icon_128x128.png": 128, "icon_128x128@2x.png": 256, "icon_256x256.png": 256, "icon_256x256@2x.png": 512,
         "icon_512x512.png": 512, "icon_512x512@2x.png": 1024}


def render(renderer, size):
    img = QImage(size, size, QImage.Format_ARGB32)
    img.fill(Qt.transparent)
    p = QPainter(img)
    renderer.render(p)
    p.end()
    return img


def main():
    QApplication(sys.argv)
    r = QSvgRenderer(str(SVG))
    ICONSET.mkdir(exist_ok=True)
    for name, size in SIZES.items():
        render(r, size).save(str(ICONSET / name))
    render(r, 256).save(str(HERE.parent.parent / "toomer" / "assets" / "toomer.png"))
    # .ico: contenedor con PNGs de 16..256 (formato soportado por Windows Vista+).
    pngs = []
    for size in (16, 32, 48, 64, 128, 256):
        from PySide6.QtCore import QBuffer, QIODevice
        buf = QBuffer()
        buf.open(QIODevice.WriteOnly)
        render(r, size).save(buf, "PNG")
        pngs.append((size, bytes(buf.data())))
    with open(HERE / "Toomer.ico", "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, len(pngs)))
        offset = 6 + 16 * len(pngs)
        for size, data in pngs:
            f.write(struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset))
            offset += len(data)
        for _, data in pngs:
            f.write(data)
    print("ok")


if __name__ == "__main__":
    main()
