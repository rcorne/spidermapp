WINDOWS — INTEGRACIÓN
======================

spidermapp.ico contiene las resoluciones 16, 32, 48 y 256px en un solo
archivo, formato estándar para:

- Ícono del .exe: referenciarlo en el .rc del proyecto
    IDI_ICON1 ICON "spidermapp.ico"
  o en Electron/Tauri/NSIS apuntar la propiedad "icon" a este archivo.

- Instalador (Inno Setup / NSIS / WiX): usar spidermapp.ico como
  SetupIconFile / Icon del acceso directo.
