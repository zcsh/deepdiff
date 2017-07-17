# -*- coding: utf-8 -*-

from .baselevel import BaseLevel
from ..helper import Verbose, short_repr


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
