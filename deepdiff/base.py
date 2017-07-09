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
    default_report_type = 'unknown'  # concrete classes shall override

    def __init__(self,
                 significant_digits=None,
                 exclude_paths=set(),
                 exclude_types=set(),
                 verbose_level=1,
                 view='text',
                 rootstr='root'):
        self.view = view
        """
        Specifies the default view. Available views are 'text' and 'tree'.
        """

        self.rootstr=rootstr
        """
        A name or pythonic path for the root object. Any generated path strings
        will start in this.
        """

        Verbose.level = verbose_level

        if significant_digits is not None and significant_digits < 0:
            raise ValueError(
                "significant_digits must be None or a non-negative integer")
        self.significant_digits = significant_digits

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
        mypath = level.path(self.rootstr)
        if self.exclude_paths and mypath in self.exclude_paths:
            skip = True
        elif self.exclude_regex_paths and any(
                [exclude_regex_path.match(mypath) for exclude_regex_path in self.exclude_regex_paths]):
            skip = True
        else:
            for content in level.level_contents():
                if isinstance(content.obj, self.exclude_types):
                    skip = True
        print("Skip " + mypath + "? --> " + str(skip) + ". My root was " + self.rootstr )
        return skip

    # TODO: Move report_type back to Diff where it belongs,
    # throw the copy() out of BaseLevel and generally inherit sensibly
    def _report_result(self, level, report_type=None):
        """
        Add a detected change to the reference-style result dictionary.
        report_type will be added to level.
        (We'll create the text-style report from there later.)
        Note: For DeepHash this will only be called once.
              DeepHash produces only one "result" which is a tree by itself
              (see comments in model.py for details).
        :param report_type: A well defined string key describing the type of change.
                            Examples: "set_item_added", "values_changed"
        :param parent: A DiffLevel object describing the objects in question in their
                       before-change and after-change object structure.

        :rtype: None
        """
        if report_type is None:
            report_type = self.default_report_type
        if not self._skip_this(level):
            level.report_type = report_type
            self.tree[report_type].add(level)

    @staticmethod
    def _add_to_frozen_set(parents_ids, item_id):
        parents_ids = set(parents_ids)
        parents_ids.add(item_id)
        return frozenset(parents_ids)


