# -*- coding: utf-8 -*-

from ..helper import py3, items, RemapDict, strings, short_repr, Verbose
from ..helper import numbers
from copy import copy

if py3:  # pragma: no cover
    from itertools import zip_longest
else:  # pragma: no cover
    from itertools import izip_longest as zip_longest

FORCE_DEFAULT = 'fake'
UP_DOWN = {'up': 'down', 'down': 'up'}

DIFF_REPORT_KEYS = {
    "type_changes",
    "dictionary_item_added",
    "dictionary_item_removed",
    "values_changed",
    "unprocessed",
    "iterable_item_added",
    "iterable_item_removed",
    "attribute_added",
    "attribute_removed",
    "set_item_removed",
    "set_item_added",
    "repetition_change",
}

HASH_REPORT_KEYS = {
    "hash",
    "unprocessed"
}


class NotPresentHere(object):  # pragma: no cover
    """
    In a change tree, this indicated that a previously existing object has been removed -- or will only be added
    in the future.
    We previously used None for this but this caused problem when users actually added and removed None. Srsly guys? :D
    """
    pass


# The following three classes are only used in DeepHash for text style result compatibility.
# I think we can probably drop those from the interface without causing too much trouble.
class Skipped(object):
    def __repr__(self):
        return "Skipped"  # pragma: no cover

    def __str__(self):
        return "Skipped"  # pragma: no cover
skipped = Skipped()


class Unprocessed(object):
    def __repr__(self):
        return "Error: Unprocessed"  # pragma: no cover

    def __str__(self):
        return "Error: Unprocessed"  # pragma: no cover
unprocessed = Unprocessed()


class NotHashed(object):
    def __repr__(self):
        return "Error: NotHashed"  # pragma: no cover

    def __str__(self):
        return "Error: NotHashed"  # pragma: no cover
not_hashed = NotHashed()


class Repetition(object):
    def __repr__(self):
        return "Repetition"  # pragma: no cover

    def __str__(self):
        return "Repetition"  # pragma: no cover
repetition = Repetition()


class ResultDict(RemapDict):
    def cleanup(self):
        """
        Remove empty keys from this object. Should always be called after the result is final.
        :return:
        """
        empty_keys = [k for k, v in getattr(self, items)() if not v]

        for k in empty_keys:
            del self[k]


class LevelContent(object):
    """
    Represents an original object tree's content at this level.
    DiffLevels have two of those because they contain two object trees
    (one for the left side or "t1" and one for the right side or "t2")
    while SearchLevels and HashLevels only contain one.
    """
    def __init__(self, obj, child_rel):
        self.obj = obj
        """
        The original object which is this tree's node at this level
        """

        self.child_rel = child_rel
        """
        A ChildRelationship object describing the relationship between t1 and it's child object,
        where t1's child object equals down.t1.
        If this relationship is representable as a string, str(self.t1_child_rel) returns a formatted param parsable python string,
        e.g. "[2]", ".my_attribute"
        """

    def copy(self):
        orig = self
        result = copy(self)  # start with a shallow copy

        # it currently looks like we actually don't need a *copy* of child_rel
        # child_rel should be considered immutable anyway
        #if orig.child_rel is not None:
        #    result.child_rel = ChildRelationship.create(
        #        klass=orig.child_rel.__class__,
        #        parent=orig.child_rel.parent,
        #        child=orig.child_rel.child,
        #        param=orig.child_rel.param)

        return result
