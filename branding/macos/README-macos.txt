MACOS — INTEGRACIÓN
====================

1. AppIcon.icns
   Copiar a TuApp.app/Contents/Resources/AppIcon.icns y referenciarlo
   como CFBundleIconFile en Info.plist (sin extensión: "AppIcon").

2. AppIcon.iconset/
   Carpeta fuente ya armada con los nombres que exige Apple. Si necesitas
   regenerar el .icns desde otra versión del ícono:
   iconutil -c icns AppIcon.iconset -o AppIcon.icns
   (Requiere macOS; en este paquete el .icns ya viene generado.)

3. dmg-background.png / dmg-background@2x.png
   Fondo del instalador .dmg (660x400pt). Con create-dmg o hdiutil:
   create-dmg --background "dmg-background.png" \
     --window-size 660 400 --icon-size 128 \
     --icon "Spidermapp.app" 110 170 \
     --app-drop-link 550 170 \
     "Spidermapp.dmg" "build/Spidermapp.app"
