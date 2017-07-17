# -*- coding: utf-8 -*-

from copy import copy
from itertools import zip_longest

from . import UP_DOWN
from . import LevelContent, NotPresentHere
from .childrelationship import ChildRelationship


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
        while level.go_up() is not None:
            level = level.go_up()
        return level

    @property
    def all_down(self):
        """
        Get the leaf object of this comparison.
        (This is a convenient wrapper for following the down attribute as often as you can.)
        :rtype: BaseLevel
        """
        level = self
        while level.go_down() is not None:
            level = level.go_down()
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
            level = level.go_down()

        self._path[force] = result
        result = None if result is None else "{}{}".format(root, result)
        return result

    def copy(self, full_path=True):
        """
        TODO This is a mess
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
        """
        TODO This is a mess
        """
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

    def go_up(self):
        """
        Wrapper around self.up allowing subclasses to fake an up if there's not an actual one.
        HashLevel's do this to represent a whole object tree as a series of chains.
        """
        return self.up

    def go_down(self):
        return self.down