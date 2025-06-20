pyinstaller --onefile --windowed --add-data "icons;icons" --add-data "default.yaml;./" --add-data "versions.json;./" -i icons/logo.png main.py

nuitka --standalone --onefile --windows-disable-console --include-data-dir=icons=./icons --include-data-file=default.yaml=default.yaml --include-data-file=versions.json=versions.json --windows-icon-from-ico=icons/logo.png main.py