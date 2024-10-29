from setuptools import setup, find_packages

setup(
    name="nitrado_api",
    version="0.1",
    packages=find_packages(),
    install_requires=[
        "aiohttp",
        "ftplib"
    ],
    author="DonMatraca",
    author_email="r.gallogomez@gmail.com",
    description="Python module to interact with Nitrado API endpoints.",
    long_description=open("README.md").read(),
    long_description_content_type="text/markdown",
    url="https://github.com/DonMatraca/nitrado_api",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
)
