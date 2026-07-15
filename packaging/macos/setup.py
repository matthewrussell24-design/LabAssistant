"""py2app configuration for a local, non-release qualification bundle."""

from setuptools import find_packages, setup


setup(
    name="LabAssistantQualification",
    version="0.1.0.dev0",
    packages=find_packages(include=("labassistant", "labassistant.*")),
    app=["packaging/macos/LabAssistantQualification.py"],
    options={
        "py2app": {
            "argv_emulation": False,
            "packages": [
                "labassistant",
                "openpyxl",
                "xlrd",
            ],
            "includes": ["cmath", "sqlite3", "xml.etree.ElementTree"],
            "excludes": [
                "numpy.tests",
                "openpyxl.tests",
                "pandas.tests",
                "plotly",
                "pytest",
                "setuptools",
                "streamlit",
                "test",
            ],
            "plist": {
                "CFBundleDisplayName": "LabAssistant Qualification (Local Only)",
                "CFBundleIdentifier": "dev.labassistant.local-qualification",
                "CFBundleName": "LabAssistantQualification",
                "CFBundleShortVersionString": "0.1.0-dev",
                "CFBundleVersion": "1",
                "LSApplicationCategoryType": "public.app-category.productivity",
                "NSHighResolutionCapable": True,
                "NSPrincipalClass": "NSApplication",
            },
        }
    },
)
