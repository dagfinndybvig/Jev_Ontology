"""Include the script-oriented Images suite in root unittest discovery."""
from pathlib import Path
import unittest


def load_tests(loader, tests, pattern):
    directory = str(Path(__file__).resolve().parent / "Images")
    return unittest.TestLoader().discover(
        directory, pattern=pattern or "test_*.py", top_level_dir=directory)
