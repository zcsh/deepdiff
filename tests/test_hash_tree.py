#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
To run only the search tests:
    python -m unittest tests.test_hash

Or to run all the tests:
    python -m unittest discover

Or to run all the tests with coverage:
    coverage run --source deepdiff setup.py test

Or using Nose:
    nosetests --with-coverage --cover-package=deepdiff

To run a specific test, run this from the root of repo:
    On linux:
    nosetests ./tests/test_hash_text.py:DeepHashTestCase.test_bytecode

    On windows:
    nosetests .\tests\test_hash_text.py:DeepHashTestCase.test_string_in_root
"""
import unittest
from deepdiff import DeepHash
from deepdiff.helper import py3, pypy3
from deepdiff.model import HashLevel
from collections import namedtuple
from tests import CustomClass
import logging

logging.disable(logging.CRITICAL)


class DeepHashTreeTestCase(unittest.TestCase):
    """DeepHash Tests."""

    def test_str(self):
        obj = "a"
        result = DeepHash(obj, view="tree", hasher=hash)
        result_level = result["hash"]

        # This DeepHash has only one single level (which is therefore a leaf node)
        self.assertEqual(result_level.up, None)
        self.assertEqual(result_level.down, None)
        self.assertEqual(result_level.leaf_hash, hash(obj))
        expected_deep_hash = str(
            hash(
                str(obj.__class__) + str(hash(obj)))
        )
        self.assertEqual(result_level.hash(), expected_deep_hash)

    def test_list(self):
        string1 = "a"
        obj = [string1, 10, 20]
        result = DeepHash(obj, view="tree", hasher=hash)
        result_level = result["hash"]

        # This DeepHash has two levels
        self.assertEqual(result_level.up, None)  # shall always return root node
        self.assertIsInstance(result_level.down, HashLevel)  # shall always return root node
        self.assertEqual(result_level.down.down, None)
        self.assertEqual(result_level.down.up, result_level)

        # This DeepHash has a single threefold branch at the root level
        # (one for every item in the list)
        string_level = result_level.down
        self.assertEqual(string_level.obj, string1)
        ten_level = result_level.additional["branches"][0].down
        self.assertEqual(ten_level.obj, 10)
        twenty_level = result_level.additional["branches"][1].down
        self.assertEqual(twenty_level.obj, 20)

        # check all raw leaf hashes
        self.assertEqual(string_level.leaf_hash, hash(string1))
        self.assertEqual(ten_level.leaf_hash, 10)
        self.assertEqual(twenty_level.leaf_hash, 20)

        # check "deep" hashes of all leaves
        string_class = str(string1.__class__)
        tmp = 10
        int_class = str(tmp.__class__)

        string_hash = str(
            hash(
                string_class + str(hash(string1))
            )
        )
        self.assertEqual(string_level.hash(), string_hash)

        ten_hash = str(
            hash(
                int_class + "10"
            )
        )
        self.assertEqual(ten_level.hash(), ten_hash)

        twenty_hash = str(
            hash(
                int_class + "20"
            )
        )
        self.assertEqual(twenty_level.hash(), twenty_hash)

        # finally, check the deep hash
        deep = str(
            hash(
                str(obj.__class__) +  # top level object is a dict
                str(hash(int_class + "0")) +  # param hash (param for first list item is 0)
                string_hash +      # hash of first list item
                str(hash(int_class + "1")) +  # param hash (param for second list item is 1)
                ten_hash +         # hash of second list item
                str(hash(int_class + "2")) +  # param hash (param for third list item is 2)
                twenty_hash
            )
        )
        self.assertEqual(result_level.hash(), deep)

# TODO: add more tests (dict at least)
