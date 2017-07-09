# -*- coding: utf-8 -*-

from deepdiff.helper import py3, items, RemapDict, strings, short_repr, Verbose
from deepdiff.helper import NotPresentHere, numbers, encode_n_hash
from collections import Iterable
from collections import MutableMapping
from ast import literal_eval
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


class DoesNotExist(Exception):
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


class DiffTreeResult(ResultDict):
    def __init__(self):
        for key in DIFF_REPORT_KEYS:
            self[key] = set()


class DiffTextResult(ResultDict):
    def __init__(self, tree_results=None):

        # TODO: centralize keys
        self.update({
            "type_changes": {},
            "dictionary_item_added": self.__set_or_dict(),
            "dictionary_item_removed": self.__set_or_dict(),
            "values_changed": {},
            "unprocessed": [],
            "iterable_item_added": {},
            "iterable_item_removed": {},
            "attribute_added": self.__set_or_dict(),
            "attribute_removed": self.__set_or_dict(),
            "set_item_removed": set(),
            "set_item_added": set(),
            "repetition_change": {}
        })

        if tree_results:
            self._from_tree_results(tree_results)

    def __set_or_dict(self):
        return {} if Verbose.level >= 2 else set()

    def _from_tree_results(self, tree):
        """
        Populate this object by parsing an existing reference-style result dictionary.
        :param DiffTreeResult tree: Source data
        :return:
        """
        self._from_tree_type_changes(tree)
        self._from_tree_default(tree, 'dictionary_item_added')
        self._from_tree_default(tree, 'dictionary_item_removed')
        self._from_tree_value_changed(tree)
        self._from_tree_unprocessed(tree)
        self._from_tree_default(tree, 'iterable_item_added')
        self._from_tree_default(tree, 'iterable_item_removed')
        self._from_tree_default(tree, 'attribute_added')
        self._from_tree_default(tree, 'attribute_removed')
        self._from_tree_set_item_removed(tree)
        self._from_tree_set_item_added(tree)
        self._from_tree_repetition_change(tree)

    def _from_tree_default(self, tree, report_type):
        if report_type in tree:
            for change in tree[report_type]:  # report each change
                # determine change direction (added or removed)
                # Report t2 (the new one) whenever possible.
                # In cases where t2 doesn't exist (i.e. stuff removed), report t1.
                if change.t2 is not NotPresentHere:
                    item = change.t2
                else:
                    item = change.t1

                # do the reporting
                report = self[report_type]
                if isinstance(report, set):
                    report.add(change.path(force=FORCE_DEFAULT))
                elif isinstance(report, dict):
                    report[change.path(force=FORCE_DEFAULT)] = item
                elif isinstance(report, list):  # pragma: no cover
                    # we don't actually have any of those right now, but just in case
                    report.append(change.path(force=FORCE_DEFAULT))
                else:  # pragma: no cover
                    # should never happen
                    raise TypeError("Cannot handle {} report container type.".
                                    format(report))

    def _from_tree_type_changes(self, tree):
        if 'type_changes' in tree:
            for change in tree['type_changes']:
                remap_dict = RemapDict({
                    'old_type': type(change.t1),
                    'new_type': type(change.t2)
                })
                self['type_changes'][change.path(
                    force=FORCE_DEFAULT)] = remap_dict
                if Verbose.level:
                    remap_dict.update(old_value=change.t1, new_value=change.t2)

    def _from_tree_value_changed(self, tree):
        if 'values_changed' in tree:
            for change in tree['values_changed']:
                the_changed = {'new_value': change.t2, 'old_value': change.t1}
                self['values_changed'][change.path(
                    force=FORCE_DEFAULT)] = the_changed
                if 'diff' in change.additional:
                    the_changed.update({'diff': change.additional['diff']})

    def _from_tree_unprocessed(self, tree):
        if 'unprocessed' in tree:
            for change in tree['unprocessed']:
                self['unprocessed'].append("%s: %s and %s" % (change.path(
                    force=FORCE_DEFAULT), change.t1, change.t2))

    def _from_tree_set_item_removed(self, tree):
        if 'set_item_removed' in tree:
            for change in tree['set_item_removed']:
                path = change.up.path(
                )  # we want't the set's path, the removed item is not directly accessible
                item = change.t1
                if isinstance(item, strings):
                    item = "'%s'" % item
                self['set_item_removed'].add("%s[%s]" % (path, str(item)))
                # this syntax is rather peculiar, but it's DeepDiff 2.x compatible

    def _from_tree_set_item_added(self, tree):
        if 'set_item_added' in tree:
            for change in tree['set_item_added']:
                path = change.up.path(
                )  # we want't the set's path, the added item is not directly accessible
                item = change.t2
                if isinstance(item, strings):
                    item = "'%s'" % item
                self['set_item_added'].add("%s[%s]" % (path, str(item)))
                # this syntax is rather peculiar, but it's DeepDiff 2.x compatible)

    def _from_tree_repetition_change(self, tree):
        if 'repetition_change' in tree:
            for change in tree['repetition_change']:
                path = change.path(force=FORCE_DEFAULT)
                self['repetition_change'][path] = RemapDict(change.additional[
                    'repetition'])
                self['repetition_change'][path]['value'] = change.t1


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
            if branch.status is Unprocessed:
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


class SearchTreeResult(ResultDict):
    pass


class SearchTextResult(ResultDict):
    pass


class BaseLevel(object):
    """
    Common abstract base class for DiffLevel, ... (more to come ;) )
    """

    def __init__(self,
                 objs=[],
                 down=None,
                 up=None,
                 child_rels=[],
                 additional=None):
        """
        :param list objs: A list of content or "payload" objects corresponding
                          to the number of object trees handled by the
                          concrete class.
                          For DiffLevel, this is 2 while it will be 1 for
                          most other cases.
        :param list child_rels: A list of ChildRelationship objects. This should
                                have the same length as objs as it describes the
                                "down" relationship for each object tree this
                                concrete class tracks.
                                If you don't provide this, we won't set it.
                                You'll usually want to omit this if there's
                                either no down or you don't know it yet;
                                or if you intend to call auto_generate_child_rels()
                                afterwards.
        """
        # First of all, set this level's content by creating the appropriate
        # amount of LevelContent objects
        # For example, for DiffLevels this will set .left and .right
        for (i, key) in enumerate(self.level_content_keys()):
            try:                            # did we get a pre-created ChildRelationship?
                child_rel = child_rels[i]   # [ ] yup
            except IndexError:              # [ ] nope
                child_rel = None
            self.__dict__[key] = LevelContent(objs[i], child_rel)
            # If this raises a KeyError, obj does not contain the right amount
            # of content objects for this kind of level object
            # (I'm not sure how to express this properly w/o breaking Py2 compatibility)

        self.down = down
        """
        Another BaseLevel object describing this change one level deeper down the object tree
        """

        self.up = up
        """
        Another BaseLevel object describing this change one level further up the object tree
        """

        self._path = {}
        """
        Will cache result of .path() per 'force' as key for performance
        """

        # Note: don't use {} as additional's default value - this would turn out to be always the same dict object
        self.additional = {} if additional is None else additional
        """
        Allow some additional information to be attached to this tree level.
        DeepDiff's DiffLevels use these for some types of changes:
        Currently, this is used for:
        - values_changed: In case the changes data is a multi-line string,
                          we include a textual diff as additional['diff'].
        - repetition_change: additional['repetition']:
                             e.g. {'old_repeat': 2, 'new_repeat': 1, 'old_indexes': [0, 2], 'new_indexes': [2]}
        the user supplied ChildRelationship objects for t1 and t2
        """

    def __setattr__(self, key, value):
        # Setting up or down, will set the opposite link in this linked list.
        if key in UP_DOWN and value is not None:
            self.__dict__[key] = value
            opposite_key = UP_DOWN[key]
            value.__dict__[opposite_key] = self
        else:
            self.__dict__[key] = value

    def level_contents(self):
        """
        Yield a list of object tree levels used here.
        This will yield two objects for DeepDiff (i.e. DiffLevel objects)
        but just one for e.g. DeepSearch.
        :return: E.g. [left, right] for DiffLevel
        :rtype Generator
        """
        raise NotImplementedError

    def level_content_keys(self):
        """
        Same as above, but return the __dict__ keys for the LevelContents
        instead of the LevelContents itself.
        This is useful if you need to replace those.
        :return: E.g. [left, right] for DiffLevel
        :rtype Generator
        """
        raise NotImplementedError

    @property
    def all_up(self):
        """
        Get the root object of this comparison.
        (This is a convenient wrapper for following the up attribute as often as you can.)
        :rtype: BaseLevel
        """
        level = self
        while level.up:
            level = level.up
        return level

    @property
    def all_down(self):
        """
        Get the leaf object of this comparison.
        (This is a convenient wrapper for following the down attribute as often as you can.)
        :rtype: BaseLevel
        """
        level = self
        while level.down:
            level = level.down
        return level

    def path(self, root="root", force=None):
        """
        A python syntax string describing how to descend to this level, assuming the top level object is called root.
        Returns None if the path is not representable as a string.
        This might be the case for example if there are sets involved (because then there's not path at all) or because
        custom objects used as dictionary keys (then there is a path but it's not representable).
        Example: root['ingredients'][0]
        Note: If there are multiple object trees (which is the case for DeepDiff's DiffLevels for example)
        we will follow the left side of the comparison branch, i.e. using the t1's to build the path.
        Using t1 or t2 should make no difference at all, except for the last step of a child-added/removed relationship.
        If it does in any other case, your comparison path is corrupt.
        :param root: The result string shall start with this var name
        :param force: Bends the meaning of "no string representation".
                      If None:
                        Will strictly return Python-parsable expressions. The result those yield will compare
                        equal to the objects in question.
                      If 'yes':
                        Will return a path including '(unrepresentable)' in place of non string-representable parts.
                      If 'fake':
                        Will try to produce an output optimized for readability.
                        This will pretend all iterables are subscriptable, for example.
        """
        # TODO: We could optimize this by building on top of self.up's path if it is cached there
        # TODO: move to base class
        if force in self._path:
            result = self._path[force]
            return None if result is None else "{}{}".format(root, result)

        result = ""
        level = self.all_up  # start at the root

        # traverse all levels of this relationship
        while level and level is not self:
            # get this level's relationship object
            next_rel = None
            for level_content in level.level_contents():
                next_rel = level_content.child_rel        # next relationship object to get a formatted param from
                if next_rel is not None:
                    break

            if next_rel is None:  # still None - looks like we're at the bottom of this tree
                break

            # Build path for this level
            item = next_rel.get_param_repr(force)
            if item:
                result += item
            else:
                # it seems this path is not representable as a string
                result = None
                break

            # Prepare processing next level
            level = level.down

        self._path[force] = result
        result = None if result is None else "{}{}".format(root, result)
        return result

    def copy(self, full_path=True):
        """
        Get a deep copy of this comparision line.
        Note: This does not copy ChildRelationships as those are considered
        immutable (--> the relationship between two objects is a fact and not
        up for discussion). (Auto-)Create a new ChildRelationship object if needed.
        :param full_path: Include levels above this object.
                          Always safe to say yes,
                          but saves performance to skip if you don't need it.
        :return: The leaf ("downmost") object of the copy.
        """
        orig = (self.all_up if full_path else self)

        previous_level_copy = None
        while orig is not None:
            # perform copy
            result = orig.copy_single_level(full_path)
            if previous_level_copy:
                previous_level_copy.down = result

            # descend to next level
            orig = orig.down
            previous_level_copy = result
        return result

    def copy_single_level(self, shall_have_up=True, shall_have_down=True):
        result = copy(self)
        if not shall_have_up:
            result.up = None
        if not shall_have_down:
            result.down = None
            # TODO set child rels to None here
            # this needs class methods telling us where those are in the concrete subclasses

        # Deep copy attributes that need to be deep-copied
        # TODO are we copying content objs here? o.O
        # more tests fail if we comment this out
        for key in self.level_content_keys():
            result.__dict__[key] = self.__dict__[key].copy()
        result.additional = copy(self.additional)

        return result

    def auto_generate_child_rel(self, klass, param):
        """
        Auto-populates the child_rel attribute of all my LevelContent attributes.
        If I'm a DiffLevel, this populates the self.child_rel1 and self.child_rel2 aliases.
        This requires self.down to be another valid BaseLevel object of the same kind.
        :param klass: A ChildRelationship subclass describing the kind of parent-child relationship,
                      e.g. DictRelationship.
        :param param: A ChildRelationship subclass-dependent parameter describing how to get from parent to child,
                      e.g. the key in a dict
        """
        sides = zip_longest(self.level_contents(), self.down.level_contents())
        for (self_level_content, down_level_content) in sides:
            if down_level_content.obj is not NotPresentHere:
                self_level_content.child_rel = ChildRelationship.create(
                    klass=klass,
                    parent=self_level_content.obj,
                    child=down_level_content.obj,
                    param=param)

    def create_deeper(self,
                      new_objs,
                      child_relationship_class,
                      child_relationship_param=None):
        """
        Start a new level and correctly link it to this one.
        :param list new_objs: A list referencing all LevelContent.obj's for the next level
        :rtype: BaseLevel subclass
        :return: New level
        """
        level = self.all_down
        result = self.__class__(new_objs, down=None, up=level)  # constructor call (just in case anyone was wondering...)
        level.down = result
        level.auto_generate_child_rel(
            klass=child_relationship_class, param=child_relationship_param)
        return result

    def branch_deeper(self,
                      new_objs,
                      child_relationship_class,
                      child_relationship_param=None,
                      full_path=True):
        """
        Fork this tree: Do not touch this comparison/search/hash/whatever line,
        but create a new one with exactly the same content, just one level deeper.
        :param full_path: Include levels above this object.
                          Always safe to say yes,
                          but saves performance to skip if you don't need it.
        :rtype: DiffLevel
        :return: New level in new comparison line
        """
        branch = self.copy(full_path=full_path)
        return branch.create_deeper(new_objs, child_relationship_class,
                                    child_relationship_param)


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


class DiffLevel(BaseLevel):
    """
    An object of this class represents a single object-tree-level in a reported change.
    A double-linked list of these object describes a single change on all of its levels.
    Looking at the tree of all changes, a list of those objects represents a single path through the tree
    (which is just fancy for "a change").
    This is the result object class for object reference style reports.

    Example:

    >>> t1 = {2: 2, 4: 44}
    >>> t2 = {2: "b", 5: 55}
    >>> ddiff = DeepDiff(t1, t2, view='tree')
    >>> ddiff
    {'dictionary_item_added': {<DiffLevel id:4560126096, t1:None, t2:55>},
     'dictionary_item_removed': {<DiffLevel id:4560126416, t1:44, t2:None>},
     'type_changes': {<DiffLevel id:4560126608, t1:2, t2:b>}}

    Graph:

    <DiffLevel id:123, original t1,t2>          <DiffLevel id:200, original t1,t2>
                    ↑up                                         ↑up
                    |                                           |
                    | ChildRelationship                         | ChildRelationship
                    |                                           |
                    ↓down                                       ↓down
    <DiffLevel id:13, t1:None, t2:55>            <DiffLevel id:421, t1:44, t2:None>
    .path() = 'root[5]'                         .path() = 'root[4]'

    Note that the 2 top level DiffLevel objects are 2 different objects even though
    they are essentially talking about the same diff operation.


    A ChildRelationship object describing the relationship between t1 and it's child object,
    where t1's child object equals down.t1.

    Think about it like a graph:

    +---------------------------------------------------------------+
    |                                                               |
    |    parent                 difflevel                 parent    |
    |      +                          ^                     +       |
    +------|--------------------------|---------------------|-------+
           |                      |   | up                  |
           | Child                |   |                     | ChildRelationship
           | Relationship         |   |                     |
           |                 down |   |                     |
    +------|----------------------|-------------------------|-------+
    |      v                      v                         v       |
    |    child                  difflevel                 child     |
    |                                                               |
    +---------------------------------------------------------------+


    The child_rel example:

    # dictionary_item_removed is a set so in order to get an item from it:
    >>> (difflevel,) = ddiff['dictionary_item_removed'])
    >>> difflevel.up.t1_child_rel
    <DictRelationship id:456, parent:{2: 2, 4: 44}, child:44, param:4>

    >>> (difflevel,) = ddiff['dictionary_item_added'])
    >>> difflevel
    <DiffLevel id:4560126096, t1:None, t2:55>

    >>> difflevel.up
    >>> <DiffLevel id:4560154512, t1:{2: 2, 4: 44}, t2:{2: 'b', 5: 55}>

    >>> difflevel.up
    <DiffLevel id:4560154512, t1:{2: 2, 4: 44}, t2:{2: 'b', 5: 55}>

    # t1 didn't exist
    >>> difflevel.up.t1_child_rel

    # t2 is added
    >>> difflevel.up.t2_child_rel
    <DictRelationship id:4560154384, parent:{2: 'b', 5: 55}, child:55, param:5>

    """

    def level_contents(self):
        """Implements abstract method from BaseLevel"""
        yield self.left
        yield self.right

    @staticmethod
    def level_content_keys():
        """Implements abstract method from BaseLevel"""
        yield 'left'
        yield 'right'

    def __init__(self,
                 objs = [],
                 down=None,
                 up=None,
                 report_type=None,
                 child_rels=[],
                 additional=None,
                 verbose_level=1):
        """
        See BaseLevel.__init__ for common params.
        """
        super(DiffLevel, self).__init__(objs, down, up, child_rels, additional)

        # self.left   # this gets set by the base class constructor
        """
        This level's content in the left hand tree.
        self.left.obj will be the payload object; self.t1 is available as an alias
        """

        # self.right  # this gets set by the base class constructor
        """
        This level's content in the right hand tree.
        self.right.obj will be the payload object; self.t2 is available as an alias
        """

        self.report_type = report_type
        """
        If this object is this change's deepest level, this contains a string describing the type of change.
        Examples: "set_item_added", "values_changed"
        """

    def __repr__(self):
        if Verbose.level:
            if self.additional:
                additional_repr = short_repr(self.additional, max_length=35)
                result = "<{} {}>".format(self.path(), additional_repr)
            else:
                t1_repr = short_repr(self.t1)
                t2_repr = short_repr(self.t2)
                result = "<{} t1:{}, t2:{}>".format(self.path(), t1_repr, t2_repr)
        else:
            result = "<{}>".format(self.path())
        return result

    @property
    def t1(self):
        """Mimicks old behavior before we introduced ContentLevels"""
        return self.left.obj

    @property
    def t2(self):
        """Mimicks old behavior before we introduced ContentLevels"""
        return self.right.obj

    @property
    def t1_child_rel(self):
        """Mimicks old behavior before we introduced ContentLevels"""
        return self.left.child_rel

    @property
    def t2_child_rel(self):
        """Mimicks old behavior before we introduced ContentLevels"""
        return self.right.child_rel

    @property
    def repetition(self):
        return self.additional['repetition']


class HashLevel(BaseLevel):
    """
    While the results of searches and diff are individual paths through the object tree
    (a search result basically gives you directions through the object tree until you arrive
    at your destination -- the object containing your search value;
    any single diff result gives you directions through both an left-hand and and right-hand object
    tree until you arrive at the boint where those two diverge)
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
    #   (through .additional["branches"]) another chain that represents a path to another
    #   leaf. This other chain will again reference additional chains whereever this
    #   subtree branches.
    #   (To conserve memory, we'll only keep one complete root-to-leaf HashLevel chain
    #   and the others will just start at their branching point.)
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

        self.additional["branches"] = []

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

    def __repr__(self):
        result = "<Representing: " + str(self.obj)
        if self.down is not None:
            have_down = True
            result += ", down: " + str(self.down.obj)
        else:
            have_down = False
        if "branches" in self.additional and len(self.additional["branches"])>0:
            if have_down:  # separator
                result += "; "

            result += "branching to: "
            first = True
            for branch in self.additional["branches"]:
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
        .additional["branches"]. This method decides which one it'll be.
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
            # Create a new chain and store it in .additional["branches"]
            new_branch = self.copy_single_level(shall_have_up=False, shall_have_down=False)
            new_branch.child_rel = None  # TODO move this to copy_single_level()
            new_branch._hash = None  # dito
            new_branch._hash_wo_params = None  # dito
            new_branch.status = True  # dito
            new_branch.hasher = self.hasher  # TODO move somewhere else
            new_branch.additional["branches"] = []  # new branch has no additional branches
            if "ignore_repetition" in self.additional:  # dito
                new_branch.additional["ignore_repetition"] = self.additional["ignore_repetition"]
            self.additional["branches"].append(new_branch)
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
        if self.additional["branches"]:
            yield from self.additional["branches"]

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
        # TODO possibe collisions? e.g. deep vs broad containers?
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


        print("Hi! I'm " + str(self) + ", status " + str(self.status) + ", hashval " + hashval)
        print("and BTW, my branches are...:")
        for branch in self.all_branches():
            if branch is not self:
                print("Branch: " + str(branch) + ", status " + str(branch.status))
                if branch.down is not None:
                    print("--Down: " + str(branch.down) + ", status " + str(branch.down.status) )
        print()

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



class SearchLevel(BaseLevel):
    pass  # TODO


class ChildRelationship(object):
    """
    Describes the relationship between a container object (the "parent") and the contained
    "child" object.
    """

    # Format to a be used for representing param.
    # E.g. for a dict, this turns a formatted param param "42" into "[42]".
    param_repr_format = None

    # This is a hook allowing subclasses to manipulate param strings.
    # :param string: Input string
    # :return: Manipulated string, as appropriate in this context.
    quote_str = None

    @staticmethod
    def create(klass, parent, child, param=None):
        if not issubclass(klass, ChildRelationship):
            raise TypeError
        return klass(parent, child, param)

    def __init__(self, parent, child, param=None):
        # The parent object of this relationship, e.g. a dict
        self.parent = parent

        # The child object of this relationship, e.g. a value in a dict
        self.child = child

        # A subclass-dependent parameter describing how to get from parent to child, e.g. the key in a dict
        self.param = param

        # will add self.param_hash for DeepHash

    def __repr__(self):
        name = "<{} parent:{}, child:{}, param:{}>"
        parent = short_repr(self.parent)
        child = short_repr(self.child)
        param = short_repr(self.param)
        return name.format(self.__class__.__name__, parent, child, param)

    def get_param_repr(self, force=None):
        """
        Returns a formatted param python parsable string describing this relationship,
        or None if the relationship is not representable as a string.
        This string can be appended to the parent Name.
        Subclasses representing a relationship that cannot be expressed as a string override this method to return None.
        Examples: "[2]", ".attribute", "['mykey']"
        :param force: Bends the meaning of "no string representation".
              If None:
                Will strictly return partials of Python-parsable expressions. The result those yield will compare
                equal to the objects in question.
              If 'yes':
                Will return a formatted param including '(unrepresentable)' instead of the non string-representable part.

        """
        return self.stringify_param(force)

    def get_param_from_obj(self, obj):  # pragma: no cover
        """
        Get item from external object.

        This is used to get the item with the same path from another object.
        This way you can apply the path tree to any object.
        """
        pass

    def stringify_param(self, force=None):
        """
        Convert param to a string. Return None if there is no string representation.
        This is called by get_param_repr()
        :param force: Bends the meaning of "no string representation".
                      If None:
                        Will strictly return Python-parsable expressions. The result those yield will compare
                        equal to the objects in question.
                      If 'yes':
                        Will return '(unrepresentable)' instead of None if there is no string representation
        """
        param = self.param
        if isinstance(param, strings):
            result = param if self.quote_str is None else self.quote_str.format(param)
        else:
            candidate = str(param)
            try:
                resurrected = literal_eval(candidate)
                # Note: This will miss string-representable custom objects.
                # However, the only alternative I can currently think of is using eval() which is inherently dangerous.
            except (SyntaxError, ValueError):
                result = None
            else:
                result = candidate if resurrected == param else None

        if result:
            result = ':' if self.param_repr_format is None else self.param_repr_format.format(result)

        return result


class DictRelationship(ChildRelationship):
    param_repr_format = "[{}]"
    quote_str = "'{}'"

    def get_param_from_obj(self, obj):
        return obj.get(self.param)


class SubscriptableIterableRelationship(DictRelationship):
    # for our purposes, we can see lists etc. as special cases of dicts

    def get_param_from_obj(self, obj):
        return obj[self.param]


class InaccessibleRelationship(ChildRelationship):
    pass


# there is no random access to set elements
class SetRelationship(InaccessibleRelationship):
    pass


class NonSubscriptableIterableRelationship(InaccessibleRelationship):

    param_repr_format = "[{}]"

    def get_param_repr(self, force=None):
        if force == 'yes':
            result = "(unrepresentable)"
        elif force == 'fake' and self.param:
            result = self.stringify_param()
        else:
            result = None

        return result


class AttributeRelationship(ChildRelationship):
    param_repr_format = ".{}"

    def get_param_from_obj(self, obj):
        return getattr(obj, self.param)
