# TODO
# - [ ] Figure out what the heck this is actually supposed to be good for

import unittest

from retrieve import *


class MyTestCase(unittest.TestCase):

    # def __init__(self):
    #     super().__init__()
    #     self.response_dicts = fake_retrieve_data()

    def test_length(self, response_dicts):
        estimated_length = 5000
        self.assertAlmostEqual(4680, len(response_dicts), delta=estimated_length * .1)

    def test_mapping(self):
        pass

    def test_everything(self):
        retrieved_data = retrieve_data()
        self.test_length(retrieved_data)


if __name__ == '__main__':
    unittest.main()
