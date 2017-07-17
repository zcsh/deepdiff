# -*- coding: utf-8 -*-

from ..helper import numbers
from . import HASH_REPORT_KEYS, unprocessed, skipped
from . import ResultDict


class HashTreeResult(ResultDict):
    def __init__(self):
        for key in HASH_REPORT_KEYS:
            self[key] = set()


class HashTextResult(ResultDict):
    """
    DeepHash's text style result is actually a flat view of all
    objects in the tree.
    Guess we should rename this.
    """
    def __init__(self, tree_results=None):
        for key in HASH_REPORT_KEYS:
            self[key] = set()
        if tree_results:
            self._from_tree_results(tree_results)

    def _from_tree_results(self, tree):
        """
        Populate this object by parsing an existing reference-style result dictionary.
        :param DiffTreeResult tree: Source data
        :return:
        """
        root = tree["hash"]  # only element in set
        self._from_tree_create_all_entries(root)

        self["unprocessed"] = []
        if "unprocessed" in tree:
            for item in tree["unprocessed"]:
                self["unprocessed"].append(item.obj)

    def _from_tree_create_all_entries(self, level):
        # This builds a flat view of everything.
        # Need to traverse all nodes.
        for branch in level.all_branches():
            # first off, here's a special case when level is unprocessed
            if branch.status is unprocessed:
                break

            self._from_tree_create_all_entries(branch.down)
            if branch.child_rel.param_hash is not None:  # create separate entries for params *alone* (for compatibility)
                self._from_tree_create_all_entries(branch.child_rel.param_hash["hash"])

        if level.status is unprocessed:
            self[id(level.obj)] = unprocessed
        elif level.status is skipped:
            self[id(level.obj)] = skipped
        elif isinstance(level.obj, numbers):
            pass  # we don't include numbers in text view
        else:
            entry = level.text_view_hash()
            if entry != "":
                #print(str(id(level.obj)) + ":" + entry)
                self[id(level.obj)] = entry
