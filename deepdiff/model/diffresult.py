# -*- coding: utf-8 -*-

from . import DIFF_REPORT_KEYS, FORCE_DEFAULT
from . import ResultDict, NotPresentHere
from ..helper import RemapDict, Verbose, strings


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
