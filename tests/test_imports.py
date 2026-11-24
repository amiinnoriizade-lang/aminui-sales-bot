import unittest

class TestApplicationImports(unittest.TestCase):
    def test_main_module_imports(self):
        import app.main  # noqa: F401

if __name__ == '__main__':
    unittest.main()
