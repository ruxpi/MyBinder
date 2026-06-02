"""py2app build script — bundles MyBinder into a standalone macOS .app.

Build with:

    pip install py2app
    python setup.py py2app

The bundle lands in dist/MyBinder.app.
"""

from setuptools import setup

APP = ["mybinder.py"]
DATA_FILES = []
OPTIONS = {
    "argv_emulation": False,
    "packages": ["bookbinder", "app", "fitz", "pymupdf", "PySide6"],
    "plist": {
        "CFBundleName": "MyBinder",
        "CFBundleDisplayName": "MyBinder",
        "CFBundleIdentifier": "com.shawnrose.mybinder",
        "CFBundleVersion": "0.1.0",
        "CFBundleShortVersionString": "0.1.0",
        "NSHighResolutionCapable": True,
        "CFBundleDocumentTypes": [
            {
                "CFBundleTypeName": "Book",
                "CFBundleTypeExtensions": ["pdf", "epub", "mobi", "fb2", "cbz"],
                "CFBundleTypeRole": "Viewer",
            }
        ],
    },
}

setup(
    app=APP,
    name="MyBinder",
    data_files=DATA_FILES,
    options={"py2app": OPTIONS},
    setup_requires=["py2app"],
)
