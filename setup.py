import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="birdsong-ignition",
    version="0.9.0",
    author="Andrew Geiger",
    author_email="andrew.geiger@corsosystems.com",
    description="A Python API to Canary Lab's historian web services in the Ignition framework.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/CorsoSource/birdsong/tree/Ignition8",
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: Implementation :: Jython",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
)
