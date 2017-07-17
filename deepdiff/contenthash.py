#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import print_function
import sys
from collections import Iterable, MutableMapping
from decimal import Decimal
import logging

from .helper import py3, strings, numbers, encode_n_hash
from .model import unprocessed, skipped, not_hashed
from .model.hashresult import HashTextResult, HashTreeResult
from .model.hashlevel import HashLevel
from .model.childrelationship import (DictRelationship, AttributeRelationship,
                                      SubscriptableIterableRelationship, NonSubscriptableIterableRelationship,
                                      SetRelationship)
from .base import DeepBase

logger = logging.getLogger(__name__)


class DeepHash(DeepBase, dict):
    r"""
    **DeepHash**
    """
    show_warning = True
    default_report_type = 'hash'  # will always use this

    def __init__(self,
                 obj,
                 hashes=None,
                 exclude_paths=set(),
                 exclude_types=set(),
                 hasher=hash,
                 ignore_repetition=True,
                 significant_digits=None,
                 view='text',
                 rootstr='root',
                 **kwargs):
        if kwargs:
            raise ValueError(
                ("The following parameter(s) are not valid: %s\n"
                 "The valid parameters are obj, hashes, exclude_types."
                 "hasher and ignore_repetition.") % ', '.join(kwargs.keys()))

        DeepBase.__init__(self,
                          significant_digits=significant_digits,
                          exclude_paths=exclude_paths,
                          exclude_types=exclude_types,
                          view=view,
                          rootstr=rootstr)

        self.ignore_repetition = ignore_repetition
        self.hasher = hasher
        self.significant_digits = significant_digits

        # TODO: restore support for precalculated hashes
        #hashes = hashes if hashes else {}
        #self.update(hashes)

        # Define some error objects
        # TODO: should remove those definitions -- just keeping them now for test compat
        #       users can just import those from model themselves
        self.unprocessed = unprocessed
        self.skipped = skipped
        self.not_hashed = not_hashed

        # Prepare result tree, perform the actual hashing and clean up
        self.tree = HashTreeResult()
        root = HashLevel([obj])
        root.additional["ignore_repetition"] = self.ignore_repetition  # TODO move somewhere else
        root.hash_function = hasher
        self.__hash(root, parents_ids=frozenset({id(obj)}))

        # DeepHash produces only a single "result" which is a tree by itself
        self.tree[self.default_report_type] = root
        self.tree.cleanup()

        # Provide default view
        # Note: wasting storage here (just in case we ever implement compacting / exporting a storage-friendly diff)
        self._text = None
        if view == 'tree':
            self.update(self.tree)
        else:
            self.update(self.text)

    @property
    def text(self):
        if self._text is None:
            self._text = HashTextResult(tree_results=self.tree)
            self._text.cleanup()  # clean up text-style result dictionary
        return self._text

    def __eq__(self, other):
        if self.view == "text":
            if isinstance(other, DeepHash):
                return self.text == other.text
            else:
                return self.text == other
        else:
            return self.tree["hash"].hash() == other.tree["hash"].hash()


    # TODO: provide sensible shortcut to self.tree["hash"]. .data? .raw? any ideas?

    def __handle_container_item(self, level, item, rel_class, rel_param, parents_ids):
        """
        This method is called by all methods handling containers.
        Those specific method's job is to figure out the appropriate
        ChildRelationship subclass and feeds us all items in this container
        one by one.
        """
        # TODO: move loop handling to model
        item_id = id(item)
        if parents_ids and item_id in parents_ids:
            return
        parents_ids_added = self._add_to_frozen_set(parents_ids, item_id)

        parent_level = level.new_entry(
            item,
            child_relationship_class=rel_class,
            child_relationship_param=rel_param)
        parent_level.child_rel.param_hash = DeepHash(rel_param,
                                                     view="tree",
                                                     hasher=self.hasher,
                                                     rootstr=parent_level.path(self.rootstr),
                                                     exclude_paths=self.exclude_paths,
                                                     exclude_types=self.exclude_types)

        if self._skip_this(parent_level):  # TODO looks like bullshit - same path as level
            level.status = skipped
        # maybe we should not include skipped objects at all...
        # but this means we need to skip if parent_level matches --
        # but that has already been generated as part of the tree :(
        # Tests currently expect them to be present, too.
        else:
            content_level = parent_level.down
            self.__hash(content_level, parents_ids_added)

    def __hash_obj(self, level, parents_ids=frozenset({}), is_namedtuple=False):
        """
        Delegates to __hash_dict() which in turn delegates to
        __handle_container_item() as any container handler does.
        """
        try:
            if is_namedtuple:
                obj = level.obj._asdict()
            else:
                obj = level.obj.__dict__
        except AttributeError:
            try:
                obj = {i: getattr(level.obj, i) for i in level.obj.__slots__}
            except AttributeError:
                # we're out of ideas
                self._report_result(level, 'unprocessed')
                level.status = unprocessed
                return

        self.__hash_dict(level, parents_ids,
                         print_as_attribute=True,
                         override_obj=obj)
        # TODO move to text result generation
        #result = "nt{}".format(result) if is_namedtuple else "obj{}".format(result)

    def __hash_dict(self,
                    level,
                    parents_ids=frozenset({}),
                    print_as_attribute=False,
                    override_obj=None):
        """As any container handler, this delegates to __handle_container_item()"""
        if override_obj:
            # for special stuff like custom objects and named tuples we receive preprocessed t1 and t2
            # but must not spoil the chain (=level) with it
            obj = override_obj
        else:
            obj = level.obj

        if print_as_attribute:
            rel_class = AttributeRelationship
        else:
            rel_class = DictRelationship

        obj_keys = set(obj.keys())

        for key in obj_keys:
            item = obj[key]
            self.__handle_container_item(level, item, rel_class, key, parents_ids)

            #hashed = "{}:{}".format(key_hash, hashed)
            #result.append(hashed)

        #result.sort()
        #result = ';'.join(result)
        #result = "dict:{%s}" % result

    def __hash_set(self, level):
        """Delegates to __hash_iterable()"""
        #return "set:{}".format(self.__hash_iterable(level))
        self.__hash_iterable(level, rel_class=SetRelationship)

    # TODO: generalize, move to base
    @staticmethod
    def __iterables_subscriptable(t1):
        try:
            if getattr(t1, '__getitem__'):
                return True
            else:  # pragma: no cover
                return False  # should never happen
        except AttributeError:
            return False

    def __hash_iterable(self, level, parents_ids=frozenset({}), rel_class=None):
        """As any container handler, this delegates to __handle_container_item()"""
        if rel_class is None:
            subscriptable = self.__iterables_subscriptable(level.obj)
            if subscriptable:
                rel_class = SubscriptableIterableRelationship
            else:
                rel_class = NonSubscriptableIterableRelationship

        #result = defaultdict(int)

        for i, item in enumerate(level.obj):
            #if self.__skip_this(x):
            #    continue
            self.__handle_container_item(level, item,
                                         rel_class=rel_class,
                                         rel_param=i,
                                         parents_ids=parents_ids)

            #result[hashed] += 1  # TODO ???

        #if self.ignore_repetition:
        #    result = list(result.keys())
        #else:
        #    result = [
        #        '{}|{}'.format(i[0], i[1]) for i in getattr(result, items)()
        #    ]
        #
        #result.sort()
        #result = ','.join(result)
        #result = "{}:{}".format(type(obj).__name__, result)

    def __hash_str(self, level):
        """
        This is not a container. Thus, this is a leaf of the object tree.
        --> No more branches! Yay!
        """
        level.leaf_hash = encode_n_hash(level.obj, self.hasher)
        #result = "str:{}".format(result)
        #self[obj_id] = result
        #return result

    def __hash_number(self, level):
        """
        This is not a container. Thus, this is a leaf of the object tree.
        --> No more branches! Yay!
        """
        # Based on diff.DeepDiff.__diff_numbers
        if self.significant_digits is not None and isinstance(level.obj, (
                float, complex, Decimal)):
            obj_s = ("{:.%sf}" % self.significant_digits).format(level.obj)

            # Special case for 0: "-0.00" should compare equal to "0.00"
            if set(obj_s) <= set("-0."):
                obj_s = "0.00"
            level.leaf_hash = obj_s
            level.additional["objtype"] = "number"  # TODO: this is not very precise
            #result = "number:{}".format(obj_s)
            #obj_id = id(obj)
            #self[obj_id] = result
        else:
            #result = "{}:{}".format(type(obj).__name__, obj)
            level.additional["objtype"] = type(level.obj).__name__  # NOTE do we really want this?
            level.leaf_hash = level.obj

    def __hash_tuple(self, level, parents_ids):
        """
        Delegates to __hash_iterable() or __hash_obj(), as appropriate.
        Both of these will then delegate to __handle_container_item(),
        as all container handlers do.
        """
        # Checking to see if it has _fields. Which probably means it is a named
        # tuple.
        try:
            level.obj._asdict
        # It must be a normal tuple
        except AttributeError:
            level.additional["objtype"] = 'tuple'  # TODO: move this stuff to base
            self.__hash_iterable(level, parents_ids)
        # We assume it is a namedtuple then
        else:
            level.additional["objtype"] = 'namedtuple'
            self.__hash_obj(level, parents_ids, is_namedtuple=True)

    def __hash(self, level, parents_ids=frozenset({})):
        """The main diff method"""

        # TODO restore optimization: identify already handled objects
        # .. then again, if we encounter the exact same object again this is
        # a loop anyway and we're gonna skip, aren't we?
        #obj_id = id(level.obj)
        #if obj_id in self:
        #    return self[obj_id]

        # Do nothing if any exclusion criteria matches
        if self._skip_this(level):
            level.status = skipped
            return
        # NOTE: some kinds of exclusion matches can only be detected
        # in _handle_container_item().

        # First, check for primitive types.
        # No matter how fancy your data structure, in the ends it's all just
        # strings and numbers. Those will always be the leafs of the object tree.
        elif isinstance(level.obj, strings):
            self.__hash_str(level)

        elif isinstance(level.obj, numbers):
            self.__hash_number(level)

        # Not a leaf? It's gonna be a container then.
        # No matter which one it is, we will in the end need to branch
        # our result tree and that will be done by __handle_container_item()
        elif isinstance(level.obj, MutableMapping):
            self.__hash_dict(level, parents_ids)

        elif isinstance(level.obj, tuple):
            self.__hash_tuple(level, parents_ids)

        elif isinstance(level.obj, (set, frozenset)):
            self.__hash_set(level)

        elif isinstance(level.obj, Iterable):
            self.__hash_iterable(level, parents_ids)

        else:
            # If all else fails...
            # This will delegate to __hash_dict because in the end of the day
            # attributes are just dicts in python.
            self.__hash_obj(level, parents_ids)

        # TODO not used here -- MOVE!
        #if result != self.not_hashed and obj_id not in self and not isinstance(
        #        level.obj, numbers):
        #    self[obj_id] = result  # TODO ??? report?
        #
        #if result is self.not_hashed:  # pragma: no cover
        #    self[obj_id] = self.not_hashed
        #    self['unprocessed'].append(level.obj)  # TODO report



if __name__ == "__main__":  # pragma: no cover
    if not py3:
        sys.exit("Please run with Python 3 to verify the doc strings.")
    import doctest
    doctest.testmod()
