import subprocess
import sys
from setuptools import setup, find_packages
from setuptools.command.install import install
from setuptools.command.develop import develop


def _self_update():
    """Reinstall this package in editable mode so local changes take effect."""
    subprocess.check_call(
        [sys.executable, '-m', 'pip', 'install', '--quiet', '-e', '.'],
        cwd=__import__('os').path.dirname(__file__) or '.',
    )


class PostInstall(install):
    def run(self):
        super().run()
        _self_update()


class PostDevelop(develop):
    def run(self):
        super().run()
        _self_update()


setup(
    name='chromascii',
    version='0.2.0',
    description='Convert images, videos, GIFs, and web links into real-time colored ASCII art in your terminal',
    author='chromascii',
    license='MIT',
    packages=find_packages(),
    install_requires=[
        'opencv-python',
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
    cmdclass={
        'install': PostInstall,
        'develop': PostDevelop,
    },
    python_requires='>=3.8',
    classifiers=[
        'License :: OSI Approved :: MIT License',
        'Programming Language :: Python :: 3',
        'Environment :: Console',
        'Topic :: Multimedia',
    ],
)
