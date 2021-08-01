from setuptools import setup
import setuptools

with open("README.md", "r", encoding="utf-8") as fh:
    long_description = fh.read()

setuptools.setup(
    name="PyScrappy",
    version="0.0.7",
    author="Vedant Tibrewal, Vedaant Singh",
    author_email="mlds93363@gmail.com",
    description="This package is made for automatic web scraping to make the whole process of scraping easy and simple.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/mldsveda/PyScrappy",
    keywords=['Scrapping', 'Flipkart', 'Snapdeal', 'Wikipedia', 'Image Scrapper', 'YouTube', 'Scrapy', 'PyScrappy', 'Instagram', 'Alibaba', 'Web Scraping', 'News', 'Stocks'],
    classifiers=[
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.6",
    py_modules=["PyScrappy", "alibaba", "flipkart", "image", "instagram", "snapdeal", "wikipedia", "youtube", 'news', 'stock'],
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