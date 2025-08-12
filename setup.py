import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="birdsong",
    version="1.4.0",
    author="Andrew Geiger",
    author_email="andrew.geiger@corsosystems.com",
    maintainer="Nick Fornicola",
    maintainer_email="nfornicola@beusaenergy.com",
    description="A Python API to Canary Lab's historian web services.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    project_urls={
        "Original Project": "https://github.com/CorsoSource/birdsong",
        "Updated Project":  "",
    },
    packages=setuptools.find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
    ],
    python_requires='>=3.12',
    install_requires=[
        'ciso8601',
        'arrow',
        'urllib3',
        'requests',
        'keyring'
    ]
)
