from setuptools import setup, find_packages

setup(
    name='chromascii',
    version='0.1.0',
    description='Convert images, videos, and GIFs into real-time colored ASCII art in your terminal',
    author='chromascii',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'opencv-python',
        'Pillow',
        'numpy',
        'rich>=13.0',
        'colorama',
    ],
    entry_points={
        'console_scripts': [
            'chromascii=chromascii.main:main',
        ],
    },
    python_requires='>=3.8',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Environment :: Console',
        'Topic :: Multimedia',
    ],
)
