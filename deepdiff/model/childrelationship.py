# -*- coding: utf-8 -*-

from ast import literal_eval

from ..helper import short_repr, strings


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
