import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="birdsong", # Replace with your own username
    version="1.0.4",
    author="Andrew Geiger",
    author_email="andrew.geiger@corsosystems.com",
    description="A Python API to Canary Lab's historian web services.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CorsoSource/birdsong",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.6',
)
