"""Setup script for PyTorch Issue Fixing Agent."""

from setuptools import setup, find_packages

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

with open("requirements.txt", "r", encoding="utf-8") as fh:
    requirements = [line.strip() for line in fh if line.strip() and not line.startswith("#")]

setup(
    name="pytorch-issue-agent",
    version="1.0.0",
    author="PyTorch Issue Agent Team",
    author_email="team@pytorch-issue-agent.com",
    description="Autonomous agent for fixing PyTorch GitHub issues",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/sladyn98/pytorch-issue-agent",
    packages=find_packages(),
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Bug Tracking",
        "License :: OSI Approved :: MIT License",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Programming Language :: Python :: 3.10",
        "Programming Language :: Python :: 3.11",
    ],
    python_requires=">=3.8",
    install_requires=requirements,
    extras_require={
        "dev": [
            "pytest>=7.0.0",
            "pytest-asyncio>=0.21.0",
            "pytest-mock>=3.10.0",
            "black>=22.0.0",
            "flake8>=5.0.0",
            "mypy>=1.0.0",
            "pre-commit>=2.20.0",
        ],
        "docs": [
            "sphinx>=5.0.0",
            "sphinx-rtd-theme>=1.0.0",
            "sphinx-autodoc-typehints>=1.19.0",
        ],
    },
    entry_points={
        "console_scripts": [
            "pytorch-issue-agent=main:main",
        ],
    },
    include_package_data=True,
    package_data={
        "": ["*.json", "*.yaml", "*.yml", "*.toml"],
    },
    keywords="pytorch github automation ai claude mcp issue-tracking",
    project_urls={
        "Bug Reports": "https://github.com/sladyn98/pytorch-issue-agent/issues",
        "Source": "https://github.com/sladyn98/pytorch-issue-agent",
        "Documentation": "https://pytorch-issue-agent.readthedocs.io/",
    },
)