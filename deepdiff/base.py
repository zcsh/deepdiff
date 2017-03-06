#!/usr/bin/env python
# -*- coding: utf-8 -*-

# In order to run the docstrings:
# python3 -m deepdiff.diff
# You might need to run it many times since dictionaries come in different orders
# every time you run the docstrings.
# However the docstring expects it in a specific order in order to pass!

from __future__ import absolute_import
from __future__ import print_function

import re

from deepdiff.helper import strings, numbers, ListItemRemovedOrAdded, NotPresentHere, IndexedHash, Verbose


class DeepBase(object):
    """
    Common base class to DeepDiff, DeepSearch and DeepHash
    TODO: Move more functionality here
    """
    def __init__(self, exclude_paths, exclude_types):
        self.__initialize_exclude(exclude_paths, exclude_types)

    def __initialize_exclude(self, exclude_paths, exclude_types):
        self.exclude_types = tuple(exclude_types)

        # Accept exclude paths (will not diff objects at those locations)
        if isinstance(exclude_paths, (strings, re._pattern_type)):  # single exclude path w/o container?
            self.exclude_paths = {exclude_paths}
        elif isinstance(exclude_paths, (set, list, tuple)):
            self.exclude_paths = set(exclude_paths)
        else:
            self.__initialize_exclude_invalid_value()  # error, RAISE, done here

        # We'll separate exclude_paths into regexp- and non-regexp ones as comparing regular strings
        # by hash is much cheaper. No need to even fire up the regexp engine if the feature is not used.
        # We'll also normalize non-regexp exclude paths and enforce those to be some kind of string.
        self.exclude_regex_paths = set()
        normalize_me = set()
        for exclude_path in self.exclude_paths:
            if isinstance(exclude_path, re._pattern_type):    # move over to regexp
                self.exclude_regex_paths.add(exclude_path)
            elif not isinstance(exclude_path, strings):
                self.__initialize_exclude_invalid_value()  # error, RAISE, done here
            else:
                if '"' in exclude_path:  # we use single quotes to indicate string indices
                    normalize_me.add(exclude_path)
        self.exclude_paths = self.exclude_paths - self.exclude_regex_paths

        for todo in normalize_me:
            self.exclude_paths.remove(todo)
            normalized = todo.replace('"', "'")           # we use single quotes to indicate string indices
            self.exclude_paths.add(normalized)

    def __initialize_exclude_invalid_value(self):
        raise ValueError(
            'You provided an invalid value for exclude_paths. Please provide a set of items,\n' +
            'each of which must either be a valid path string or a precompiled regular expression.\n' +
            'Examples:\n' +
            '- "root[\'remove\']"\n' +
            '- re.compile(".*remove.*")'
        )

    def _skip_this(self, level):
        """
        Check whether this comparison should be skipped because one of the objects to compare meets exclusion criteria.
        :rtype: bool
        """
        skip = False
        mypath = level.path()
        if self.exclude_paths and mypath in self.exclude_paths:
            skip = True
        elif self.exclude_regex_paths and any(
                [exclude_regex_path.match(mypath) for exclude_regex_path in self.exclude_regex_paths]):
            skip = True
        else:
            if isinstance(level.t1, self.exclude_types) or isinstance(
                    level.t2, self.exclude_types):
                skip = True

        return skip

