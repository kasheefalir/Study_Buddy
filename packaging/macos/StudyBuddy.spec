from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

root = Path(SPECPATH).parents[1]
data = collect_data_files("app", includes=["**/*.md", "ui/static/**/*"])
data += [(str(root / "2D Pixel Top-Down Japanese School Tileset"), "2D Pixel Top-Down Japanese School Tileset")]
data += collect_data_files("trafilatura")
a = Analysis([str(root / "app" / "desktop.py")], pathex=[str(root)], datas=data,
             hiddenimports=collect_submodules("app") + collect_submodules("uvicorn"),
             excludes=["pytest"], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="StudyBuddy",
          console=False, debug=False, strip=False, upx=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="StudyBuddy")
app = BUNDLE(coll, name="Study Buddy.app", bundle_identifier="org.studybuddy.desktop",
             info_plist={"CFBundleShortVersionString": "0.1.0",
                         "NSHighResolutionCapable": True,
                         "LSMinimumSystemVersion": "15.0"})
