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
from tests import CustomClass, Bad
import logging

logging.disable(logging.CRITICAL)


class DeepHashTreeTestCase(unittest.TestCase):
    """DeepHash Tests."""

    def setUp(self):
        self.string_class = str("a".__class__)
        tmp = 10
        self.int_class = str(tmp.__class__)

    def test_str(self):
        obj = "a"
        result = DeepHash(obj, view="tree", hasher=hash, ignore_repetition=False)
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
        result = DeepHash(obj, view="tree", hasher=hash, ignore_repetition=False)
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

        string_hash = str(
            hash(
                self.string_class + str(hash(string1))
            )
        )
        self.assertEqual(string_level.hash(), string_hash)

        ten_hash = str(
            hash(
                self.int_class + "10"
            )
        )
        self.assertEqual(ten_level.hash(), ten_hash)

        twenty_hash = str(
            hash(
                self.int_class + "20"
            )
        )
        self.assertEqual(twenty_level.hash(), twenty_hash)

        # finally, check the deep hash
        deep = str(
            hash(
                str(obj.__class__) +  # top level object is a dict
                str(hash(self.int_class + "0")) +  # param hash (param for first list item is 0)
                string_hash +      # hash of first list item
                str(hash(self.int_class + "1")) +  # param hash (param for second list item is 1)
                ten_hash +         # hash of second list item
                str(hash(self.int_class + "2")) +  # param hash (param for third list item is 2)
                twenty_hash
            )
        )
        self.assertEqual(result_level.hash(), deep)

    def test_bad_in_list(self):
        bad = Bad()
        obj = [42, 1337, 31337, bad]

        result = DeepHash(obj, view='tree', ignore_repetition=False)
        top = result["hash"]

        # check object structure:
        # get all levels, verify objects in place
        self.assertEqual(top.obj, obj)

        fourtytwo = top.down
        self.assertEqual(fourtytwo.obj, 42)

        leet = top.additional["branches"][0].down
        self.assertEqual(leet.obj, 1337)

        elite = top.additional["branches"][1].down
        self.assertEqual(elite.obj, 31337)

        badobject = top.additional["branches"][2].down
        self.assertIs(badobject.obj, bad)

        # depth is 2 --> all children are leaves
        self.assertIsNone(fourtytwo.down)
        self.assertIsNone(leet.down)
        self.assertIsNone(elite.down)
        self.assertIsNone(badobject.down)

        # check up refs
        self.assertIs(fourtytwo.up, top)
        self.assertIs(leet.up, top.additional["branches"][0])
        self.assertIs(elite.up, top.additional["branches"][1])
        self.assertIs(badobject.up, top.additional["branches"][2])

        # none of those shall have branches
        self.assertEqual(fourtytwo.additional["branches"], [])
        self.assertEqual(leet.additional["branches"], [])
        self.assertEqual(elite.additional["branches"], [])
        self.assertEqual(badobject.additional["branches"], [])

        # none of the top level branches shall have any further branches
        self.assertEqual(leet.up.additional["branches"], [])
        self.assertEqual(elite.up.additional["branches"], [])
        self.assertEqual(badobject.up.additional["branches"], [])

        # top level branches reference the top level object
        self.assertEqual(leet.up.obj, obj)
        self.assertEqual(elite.up.obj, obj)
        self.assertEqual(badobject.up.obj, obj)

        # check objtype annotations
        #self.assertEqual(top.additional["objtype"])  UNDECIDED
        self.assertEqual(fourtytwo.additional["objtype"], "int")
        self.assertEqual(leet.additional["objtype"], "int")
        self.assertEqual(elite.additional["objtype"], "int")
        self.assertFalse("objtype" in badobject.additional)  # bad object gets no annotation

        # Check unified tree hash
        # Unprocessed objects shall be ignored ( = return an empty string as "hash")
        fourtytwo_param_hash = str(hash(self.int_class + "0")) # check
        fourtytwo_content_hash = str(hash(self.int_class + "42")) # check
        fourtytwo_hash = fourtytwo_param_hash + fourtytwo_content_hash

        leet_param_hash = str(hash(self.int_class + "1")) # check
        leet_content_hash = str(hash(self.int_class + "1337")) # check
        leet_hash = leet_param_hash + leet_content_hash

        elite_param_hash = str(hash(self.int_class + "2")) # check
        elite_content_hash = str(hash(self.int_class + "31337")) # check
        elite_hash = elite_param_hash + elite_content_hash

        badobj_param_hash = str(hash(self.int_class + "3")) # check
        badobj_content_hash = ""
        badobj_hash = badobj_param_hash + badobj_content_hash

        deep = str(
            hash(
                str(obj.__class__) +  # top level object is a dict
                fourtytwo_hash + leet_hash + elite_hash + badobj_hash
            )
        )
        self.assertEqual(top.hash(), deep)

    def test_float(self):
        t1 = 3.1415927
        t2 = 3.143

        hash1 = DeepHash(t1, view='tree')
        hash2 = DeepHash(t2, view='tree')

        self.assertNotEqual(hash1["hash"].leaf_hash, hash2["hash"].leaf_hash)
        # Note: ^ different values v
        self.assertNotEqual(hash1["hash"].hash(), hash2["hash"].hash())
        # Note: ^ compares same values v
        self.assertNotEqual(hash1, hash2)

    def test_significant_digits(self):
        t1 = 3.1415927
        t2 = 3.142

        hash1 = DeepHash(t1, view='tree', significant_digits=2)
        hash2 = DeepHash(t2, view='tree', significant_digits=2)

        self.assertEqual(hash1["hash"].leaf_hash, hash2["hash"].leaf_hash)
        self.assertEqual(hash1["hash"].hash(), hash2["hash"].hash())
        self.assertEqual(hash1, hash2)

    def test_significant_false(self):
        t1 = 3.1415927
        t2 = 3.14

        hash1 = DeepHash(t1, view='tree', significant_digits=3)
        hash2 = DeepHash(t2, view='tree', significant_digits=3)

        self.assertNotEqual(hash1["hash"].leaf_hash, hash2["hash"].leaf_hash)
        self.assertNotEqual(hash1["hash"].hash(), hash2["hash"].hash())
        self.assertNotEqual(hash1, hash2)

    def test_significant_false2(self):
        t1 = 3.1415927
        t2 = 3.143

        hash1 = DeepHash(t1, view='tree', significant_digits=256)
        hash2 = DeepHash(t2, view='tree', significant_digits=256)

        self.assertNotEqual(hash1["hash"].leaf_hash, hash2["hash"].leaf_hash)
        self.assertNotEqual(hash1["hash"].hash(), hash2["hash"].hash())
        self.assertNotEqual(hash1, hash2)

    def test_different_dict_different_hash(self):
        t1 = {'a': 1, 'b': 2}
        t2 = {'a': 1, 'b': 3}
        hash1 = DeepHash(t1, view='tree')
        hash2 = DeepHash(t2, view='tree')
        self.assertNotEqual(hash1["hash"].hash(), hash2["hash"].hash())

    def test_same_dict_same_hash(self):
        t1 = {'b': 5, 'c': 4}
        t2 = {'b': 5, 'c': 4}
        hash1 = DeepHash(t1, view='tree')
        hash2 = DeepHash(t2, view='tree')
        self.assertEqual(hash1["hash"].hash(), hash2["hash"].hash())

    def test_different_dict_exclude_path(self):
        t1 = {'a': 1, 'b': 2}
        t2 = {'a': 1, 'b': 3}
        hash1 = DeepHash(t1, view='tree', exclude_paths={"root['b']"})
        hash2 = DeepHash(t2, view='tree', exclude_paths={"root['b']"})
        self.assertEqual(hash1["hash"].hash(), hash2["hash"].hash())

    def test_same_dict_in_list_same_hash(self):
        t1 = [{'b': 5, 'c': 4}]
        t2 = [{'b': 5, 'c': 4}]
        hash1 = DeepHash(t1, view='tree')
        hash2 = DeepHash(t2, view='tree')
        self.assertEqual(hash1["hash"].hash(), hash2["hash"].hash())

    def test_different_dict_in_list_different_hash(self):
        t1 = [{'a': 1, 'b': 2}]
        t2 = [{'a': 1, 'b': 3}]
        hash1 = DeepHash(t1, view='tree')
        hash2 = DeepHash(t2, view='tree')
        self.assertNotEqual(hash1["hash"].hash(), hash2["hash"].hash())

    def test_different_dict_in_list_exclude_path(self):
        t1 = [{'a': 1, 'b': 2}]
        t2 = [{'a': 1, 'b': 3}]
        hash1 = DeepHash(t1, view='tree', exclude_paths={"root[0]['b']"})
        hash2 = DeepHash(t2, view='tree', exclude_paths={"root[0]['b']"})
        self.assertEqual(hash1["hash"].hash(), hash2["hash"].hash())

    def test_different_dict_in_list_exclude_path_additional_content(self):
        t1 = [{'a': 1, 'b': 2}, {'b': 5, 'c': 4}]
        t2 = [{'a': 1, 'b': 3}, {'b': 5, 'c': 4}]
        hash1 = DeepHash(t1, view='tree', exclude_paths={"root[0]['b']"})
        hash2 = DeepHash(t2, view='tree', exclude_paths={"root[0]['b']"})
        self.assertEqual(hash1["hash"].hash(), hash2["hash"].hash())


# TODO: add more tests (dict at least)


class DeepHashSHA1TestCase(unittest.TestCase):
    """DeepHash with SHA1 Tests."""
    # TOD
    pass