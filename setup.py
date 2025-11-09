from setuptools import setup, find_packages

setup(
    name="queuectl",
    version="0.1.0",
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        "click>=8.0.0",
    ],
    entry_points={
        "console_scripts": [
            "queuectl=queuectl.cli:main",
        ],
    },
    author="QueueCTL",
    author_email="example@example.com",
    description="A CLI-based background job queue system",
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)