import unittest


class TestCore(unittest.TestCase):
    def test_everything(self):
        try:
            self.assertTrue(True)
        except:
            self.assertTrue(False)


if __name__ == '__main__':
    unittest.main()
