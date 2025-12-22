from setuptools import setup, find_packages

setup(
    name="diskman",
    version="3.0.0",
    description="DiskMan V3 - Enhanced Disk Space Analyzer",
    author="SamSeen",
    url="https://github.com/MrSamSeen/DiskMan",
    packages=find_packages(),
    py_modules=["DiskMan"],
    install_requires=[
        "colorama",
        "humanize",
        "send2trash",
    ],
    entry_points={
        "console_scripts": [
            "diskman=DiskMan:main",
        ],
    },
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
