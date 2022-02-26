from setuptools import setup
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PyScrappy",
    version="0.1.0",
    author="Vedant Tibrewal, Vedaant Singh",
    author_email="mlds93363@gmail.com",
    description="Powerful web scraping tool.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mldsveda/PyScrappy",
    keywords=['PyScrappy', 'Scraping', 'E-Commerce', 'Wikipedia', 'Image Scrapper', 'YouTube', 'Scrapy', 'Twitter', 'Social Media', 'Web Scraping', 'News', 'Stocks', 'Songs', 'Food', 'Instagram', 'Movies'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    py_modules=["PyScrappy", "alibaba", "amazon", "flipkart", "image", "imdb", "instagram", "news", "snapdeal", "soundcloud", "spotify", "stock", "swiggy", "twitter", "wikipedia", "youtube", "zomato"],
    package_dir={"": "src"},
    install_requires=[
        'selenium',
        'webdriver-manager',
        'beautifulsoup4',
        'requests',
        'pandas',
    ],
    packages=setuptools.find_packages(where="src")
)
