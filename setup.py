from setuptools import setup, find_packages


setup(
    name='chromascii',
    version='0.2.0',
    description='Convert images, videos, GIFs, and web links into real-time colored ASCII art in your terminal',
    author='chromascii',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'opencv-python<5',
        'Pillow',
        'numpy',
        'rich>=13.0',
        'colorama',
        'yt-dlp',
    ],
    extras_require={
        'audio': ['av', 'sounddevice'],
        'virtualcam': ['pyvirtualcam'],
    },
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
