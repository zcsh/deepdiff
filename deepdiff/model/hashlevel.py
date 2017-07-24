# -*- coding: utf-8 -*-

from collections.abc import MutableMapping
from collections import Iterable
from copy import copy

from .baselevel import BaseLevel
from ..helper import encode_n_hash, strings, numbers
from . import repetition, skipped


class HashLevel(BaseLevel):
    """
    TODO revise documentation
    While the results of searches and diff are individual paths through the object tree
    (a search result basically gives you directions through the object tree until you arrive
    at your destination -- the object containing your search value;
    any single diff result gives you directions through both an left-hand and and right-hand object
    tree until you arrive at the point where those two diverge)
    hashing means traversing the whole tree.
    This means that a HashLevel always contains one single obj -- the object of the tree
    we're currently looking at -- but provides any number of child_rels.
    It also means there is just a single up, but any number of down's.
    And here's where it start to get ugly so I just mark it with TODO
    #
    # - A single chain of *SearchLevel* objects represents a single path through a single object tree,
    #   leading from to root up to an object matching the search criteria.
    #   - Therefore, a SearchTreeResult contains all of those paths which lead to matching objects.
    # - A single chain of *DiffLevel* objects represents a single path through two similar
    #   object trees, from the root up a point where they diverge.
    #   - Therefore, a DiffTreeResult contains all of those paths, each ending at a point where the
    #     payload trees t1 and t2 diverge.
    # - A chain of *HashLevel* objects denotes just any path through the object tree
    #   from the root to any leaf.
    #   At all points where the payload object tree branches this chain references
    #   (.right) another chain that represents a path to another
    #   leaf. This other chain will again reference additional chains wherever this
    #   subtree branches.
    #   To conserve memory, we'll only keep one complete root-to-leaf HashLevel chain
    #   and the others will just start at their branching point.
    #   As replacement there's a .left at the top of a diverging chain that brings you back to the original one
    #   which should have a .up
    #   - Therefore, a HashTreeResult contains just a single HashLevel "chain", which as explained
    #     is not really a single chain at all but a tree itself.
    """
    def __init__(self,
                 objs = [],
                 down=None,
                 up=None,
                 child_rels=[],
                 hasher=hash):
        """
        See BaseLevel.__init__ for common params.
        """
        super(HashLevel, self).__init__(objs, down, up, child_rels)

        self.right = None
        """
        If there's a branch in our object tree right here, right represents the branch while
        I represent the straight down path.
        (Yes, it's completely arbitrary what we consider as "straight" and what as "branching".)
        In case of a more-than-twofold branch, either my right will have another right
        or I'm already someone's right as well.
        """

        self.left = None
        """
        If there's a branch in our object tree right here, left represents the straight down path
        while I represent the branch.
        (Yes, it's completely arbitrary what we consider as "straight" and what as "branching".)
        In case of a more-than-twofold branch, I might have both a left and a right.
        """

        # self.content will be set by base class constructor

        self.hasher = hasher

        self.leaf_hash = None
        """
        On leaf nodes (= directly hashable object) this shall contain this object's hash.
        """

        self._hash = None
        """
        Cached result of hash()
        """

        self._hash_wo_params = None
        """
        Cached result of hash() if ignoring child relationship parameters
        """

        self.status = True  # true means everythin' peachy
        """
        Shall be set to unprocessed (global object) if we cannot hash this levels obj
        and/or cannot procede down the object tree from here although this does not
        seem to be a leaf.
        Shall be set to Skipped if this object meets exclusion criteria.
        TODO: We probably should not include those at all in both of these two cases.
        For the moment however, it was easier this way.
        And it provides backwards compatibility for text style view.
        """

    def copy(self):
        """
        Provides a copy of this single HashLevel that can be reused in another chain.
        As we're copying only a single level, all information referring to other objects in our chain
        will be missing from the copy (notably up, down, left, right and child_rel).
        :return: 
        """
        obj = HashLevel(objs=[self.obj],
                        hasher=self.hasher)
        obj.status = self.status
        obj.leaf_hash = self.leaf_hash
        obj.additional = copy(self.additional)
        return obj

    def __repr__(self):
        result = "<Representing: " + str(self.obj)
        if self.down is not None:
            have_down = True
            result += ", down: " + str(self.down.obj)
        else:
            have_down = False
        if self.right is not None:
            if have_down:  # separator
                result += "; "

            result += "branching to: "
            first = True
            branch = self
            while True:
                branch = branch.right
                if branch is None:
                    break
                if not first:
                    result += ", "
                first = False
                result += str(branch.down.obj)
        result += ">"
        return result

    def level_contents(self):
        yield self.content

    def level_content_keys(self):
        yield 'content'

    @property
    def obj(self):
        return self.content.obj

    @property
    def child_rel(self):
        try:
            return self.content.child_rel
        except IndexError:
            return None

    def new_entry(self,
                  new_obj,
                  child_relationship_class,
                  child_relationship_param=None):
        """
        Wrapper around BaseLevel.branch_deeper():
        HashLevels store one subtree in the default .down attribute and the rest as
        .right or .right's right. This method decides which one it'll be.
        :return The parent level object (which may or may not be the
                object you called this method on
        """
        if self.down is None:
            # this is the first "branch" we learn - just use down
            # and extend this chain
            self.create_deeper(new_objs = [new_obj],
                               child_relationship_class=child_relationship_class,
                               child_relationship_param=child_relationship_param)
            self.down.hasher = self.hasher  # TODO move somewhere else
            if "ignore_repetition" in self.additional:  # dito
                self.down.additional["ignore_repetition"] = self.additional["ignore_repetition"]
            return self
        else:
            # This is an additional branch.
            # Create a new chain and store it as right.
            # Check first if I already have a right -- if so, the new branch will be their right.
            new_branch = self.copy()
            trunk = self
            while trunk.right is not None:
                trunk = trunk.right
            trunk.right = new_branch
            new_branch.left = trunk
            new_branch.right = None
            new_branch.status = True  # dito
            new_branch.create_deeper(
                new_objs=[new_obj],
                child_relationship_class=child_relationship_class,
                child_relationship_param=child_relationship_param)
            new_branch.down.hasher = self.hasher  # TODO move somewhere else
            if "ignore_repetition" in self.additional:  # dito
                new_branch.down.additional["ignore_repetition"] = self.additional["ignore_repetition"]
            return new_branch

    def all_branches(self):
        """
        Generator providing all current branches of this chain.
        """
        if self.down is not None:
            yield self
        branch = self
        while branch.right is not None:
            branch = branch.right
            yield branch

    def hash(self, include_params=None):
        """
        Produce a real, single deep hash value starting at this level.
        Result shall be a single string with the output length of the hash
        function used.
        This is generated by concatenating:
          - a string representing this objects type (e.g. "dict")
          - self.leaf_hash if it is set (which it should only be if this is a leaf node)
            OR
            for any subtree,
            - the hash of the ChildRelationship's param
            - the actual subtree's hash()
        and hashing those again.
        If we are a leaf node, this will simple return self.raw_hash as string.
        If this is not set, raise an error.
        :rtype: str
        """
        # TODO possible collisions? e.g. deep vs broad containers?
        #      this is probably not a secure hash yet

        if include_params is None:
            if "ignore_repetition" in self.additional and self.additional["ignore_repetition"]:
                include_params = False
            else:
                include_params = True

        # separate caches for include_params True/False
        if include_params:
            if self._hash is not None:  # cached?
                return self._hash
        else:
            if self._hash_wo_params is not None:
                return self._hash_wo_params

        if self.status is not True:
            self._hash = ""
            return self._hash

        concat = str(self.obj.__class__)

        if self.leaf_hash is not None:
            concat += str(self.leaf_hash)
        else:
            for branch in self.all_branches():
                if "ignore_repetition" in self.additional and self.additional["ignore_repetition"] and \
                                branch.status is repetition:
                    continue  # skip repetitions if requested
                if branch.down.status is skipped:
                    continue

                if include_params:
                    param_hash = branch.child_rel.param_hash["hash"].hash(include_params)
                else:
                    param_hash = ""
                child_hash = branch.down.hash()
                concat += param_hash + child_hash

        hashval = encode_n_hash(concat, self.hasher)

        if include_params:
            self._hash = hashval
        else:
            self._hash_wo_params = hashval
        self.mark_repetitions()  # for ignore_repetition only

        return hashval

    def mark_repetitions(self):
        """
        Tag my branches as repetition if they have the same hash as I do.
        If ignore_repetition is set, these tags will later be used to... well, ignore repetitions.
        """
        # TODO test unified hash w/ ignore repetition
        if "ignore_repetition" in self.additional and self.additional["ignore_repetition"]:
            for branch in self.all_branches():
                for cmpto in self.all_branches():
                    if cmpto is branch:
                        continue  # I'm not my own repetition
                    if cmpto.status == repetition:
                        continue  # avoid marking circular repetitions
                    # TODO: much to complicated. rework branches: chained branching, just one branch per object
                    if branch.down.hash(include_params=False) == cmpto.down.hash(include_params=False):
                        # A branch is my repetition if my child is equal to their child.
                        # Note that we must not compare the branch's hash to mine without going
                        # down first as my branch represents the same object as I do
                        # (if I represent a list my branch represents a same list,
                        # but my down may represent the first list item while the branch's down
                        # may represent the second one)
                        # but if I have branches, my branches by definition don't.
                        branch.status = repetition
                    else:
                        pass

    def text_view_hash(self):
        """
        TODO for text view
        :rtype: str
        """
        if self.status is repetition:
            return ""
        if self.status is not True:
            return str(self.status)

        self.mark_repetitions()  # for ignore_repetition only

        # TODO: use .additional['objtype'] for everything instead of rechecking
        # this of course requires that those'll be set consistently by DeepHash
        # or, even better, DeepBase

        # Do we need to include the child relationship param in the text result?
        want_param = False  # will be set to True for types which need this
        # e.g. dict keys will be included

        # Do we want to sort results alphabetically?
        want_sort = False  # will be set to True for types which need this
        # We mostly don't need this and for some types, e.g. list, this is prohibitive.
        # For example, we do want to sort dicts though

        if isinstance(self.obj, strings):
            frame = "str:%s"

        elif isinstance(self.obj, numbers):
            frame = self.additional['objtype'] + ":%s"

        elif isinstance(self.obj, MutableMapping):
            frame = "dict:{%s}"
            want_param = True
            want_sort = True

        elif isinstance(self.obj, tuple):
            if self.additional['objtype'] == 'tuple':
                frame = "tuple:%s"
                want_sort = True
                # Why do we sort tuples in text view?
                # Tuples are ordered containers. This is basically a collision.
            elif self.additional['objtype'] == 'namedtuple':
                frame = "ntdict:{%s}"
                want_param = True
                want_sort = True

        elif isinstance(self.obj, (set, frozenset)):
            frame = "set:%s"

        elif isinstance(self.obj, Iterable):
            frame = "list:%s"
            want_sort = True
            # Why do we sort list objects in text view?
            # Lists are ordered containers. This is basically a collision.

        else:
            frame = "objdict:{%s}"
            want_param = True
            want_sort = True

        if want_param:
            sep_items = ";"
        else:
            sep_items = ','

        if self.leaf_hash is not None:
            contents = [str(self.leaf_hash)]
        else:
            contents = []
            for branch in self.all_branches():
                if "ignore_repetition" in self.additional and self.additional["ignore_repetition"] and \
                                branch.status is repetition:
                    continue
                if branch.down is not None:  # should always be true
                    subresult = branch.down.text_view_hash()
                    if want_param:
                        param_str = branch.child_rel.param_hash["hash"].text_view_hash()
                        subresult = param_str + ":" + subresult
                    contents.append(subresult)
        if want_sort:
            contents.sort()

        content = sep_items.join(contents)

        result = frame % content
        return result

    def go_up(self):
        if self.up is not None:
            return self.up
        else:
            if self.left is not None:
                return self.left.go_up()
            else:
                return None