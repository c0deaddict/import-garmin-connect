import setuptools

with open("README.org", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="import-garmin-connect",
    version="0.0.1",
    author="Jos van Bakel",
    author_email="jos@codeaddict.org",
    description="Import Garmin Connect data into InfluxDB",
    long_description=long_description,
    long_description_content_type="text/x-org",
    url="https://github.com/c0deaddict/import-garmin-connect",
    packages=["import_garmin_connect"],
    entry_points={
        "console_scripts": [
            "import_garmin_connect = import_garmin_connect.__main__:main"
        ]
    },
    install_requires=["requests", "influxdb"],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
)
