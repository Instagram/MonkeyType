# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from typing import List, Tuple, Union, cast

import libcst
from libcst import (
    BaseCompoundStatement,
    BaseSmallStatement,
    BaseSuite,
    CSTTransformer,
    FlattenSentinel,
    Import,
    ImportFrom,
    ImportStar,
    MaybeSentinel,
    Module,
    RemovalSentinel,
    RemoveFromParent,
    SimpleStatementLine,
)
from libcst.codemod import CodemodContext, ContextAwareTransformer
from libcst.codemod.visitors import AddImportsVisitor, GatherImportsVisitor, ImportItem
from libcst.helpers import get_absolute_module_from_package_for_import


class MoveImportsToTypeCheckingBlockVisitor(ContextAwareTransformer):
    CONTEXT_KEY = "MoveImportsToTypeCheckingBlockVisitor"

    def __init__(
        self,
        context: CodemodContext,
    ) -> None:
        super().__init__(context)

        self.import_items_to_be_moved: List[ImportItem] = []

    @staticmethod
    def store_imports_in_context(
        context: CodemodContext,
        import_items_to_be_moved: List[ImportItem],
    ) -> None:
        context.scratch[MoveImportsToTypeCheckingBlockVisitor.CONTEXT_KEY] = (
            import_items_to_be_moved,
        )

    @staticmethod
    def _add_type_checking_import(source_module: Module) -> Module:
        context = CodemodContext()
        AddImportsVisitor.add_needed_import(context, "typing", "TYPE_CHECKING")
        transformer = AddImportsVisitor(context)
        transformed_source_module = transformer.transform_module(source_module)
        return transformed_source_module

    def _remove_imports(self, tree: Module) -> Module:
        transformer = RemoveImportsTransformer(self.import_items_to_be_moved)
        transformed_source_module = tree.visit(transformer)
        return transformed_source_module

    def _get_import_module(self) -> Module:
        empty_code = libcst.parse_module("")
        context = CodemodContext()
        context.scratch[AddImportsVisitor.CONTEXT_KEY] = self.import_items_to_be_moved
        transformer = AddImportsVisitor(context)
        transformed_source_module = transformer.transform_module(empty_code)
        return transformed_source_module

    @staticmethod
    def _replace_pass_with_imports(
        placeholder_module: Module, import_module: Module
    ) -> Module:
        return placeholder_module.with_deep_changes(
            old_node=cast(BaseSuite, placeholder_module.body[0].body),
            body=import_module.body,
        )

    def _split_module(
        self, module: Module
    ) -> Tuple[
        List[Union[SimpleStatementLine, BaseCompoundStatement]],
        List[Union[SimpleStatementLine, BaseCompoundStatement]],
    ]:
        type_checking_block_add_location = 0
        gatherer = GatherImportsVisitor(self.context)
        module.visit(gatherer)
        all_imports = gatherer.all_imports

        for i, statement in enumerate(module.body):
            if isinstance(statement, SimpleStatementLine):
                for possible_import in statement.body:
                    for last_import in all_imports:
                        if possible_import is last_import:
                            type_checking_block_add_location = i + 1
                            break

        return (
            list(module.body[:type_checking_block_add_location]),
            list(module.body[type_checking_block_add_location:]),
        )

    def _add_if_type_checking_block(self, module: Module) -> Module:
        if not self.import_items_to_be_moved:
            return module

        import_module = self._get_import_module()

        placeholder_module = libcst.parse_module("\nif TYPE_CHECKING:\n    pass\n")
        type_checking_block_module = self._replace_pass_with_imports(
            placeholder_module,
            import_module,
        )

        # Find the point of insertion for the TYPE_CHECKING block
        statements_before_imports, statements_after_imports = self._split_module(module)

        updated_body_list = [
            *statements_before_imports,
            type_checking_block_module,
            *statements_after_imports,
        ]

        return module.with_changes(body=updated_body_list)

    @staticmethod
    def _remove_typing_module(import_item_list: List[ImportItem]) -> List[ImportItem]:
        ret: List[ImportItem] = []
        for import_item in import_item_list:
            if import_item.module_name != "typing":
                ret.append(import_item)
        return ret

    def transform_module_impl(
        self,
        tree: Module,
    ) -> Module:
        # Add from typing import TYPE_CHECKING
        tree = self._add_type_checking_import(tree)

        context_contents = self.context.scratch.get(
            MoveImportsToTypeCheckingBlockVisitor.CONTEXT_KEY
        )
        if context_contents is not None:
            (import_items_to_be_moved,) = context_contents

            self.import_items_to_be_moved = import_items_to_be_moved

            # Remove typing library since we do not want it
            # to be imported inside the if TYPE_CHECKING block
            self.import_items_to_be_moved = self._remove_typing_module(
                self.import_items_to_be_moved
            )

            # Remove the newer imports since those are to be
            # shifted inside the if TYPE_CHECKING block
            tree = self._remove_imports(tree)

            # Add the new imports inside if TYPE_CHECKING block
            tree = self._add_if_type_checking_block(tree)

        return tree


class RemoveImportsTransformer(CSTTransformer):
    def __init__(
        self,
        import_items_to_be_removed: List[ImportItem],
    ) -> None:
        super().__init__()
        self.import_items_to_be_removed = import_items_to_be_removed

    def leave_Import(
        self, original_node: Import, updated_node: Import
    ) -> Union[
        BaseSmallStatement, FlattenSentinel[BaseSmallStatement], RemovalSentinel
    ]:
        names_to_keep = []
        for name in updated_node.names:
            module_name = name.evaluated_name
            found = False
            for import_item in self.import_items_to_be_removed:
                if import_item.module_name == module_name:
                    found = True
                    break
            if not found:
                names_to_keep.append(name.with_changes(comma=MaybeSentinel.DEFAULT))

        if not names_to_keep:
            return RemoveFromParent()
        else:
            return updated_node.with_changes(names=names_to_keep)

    def leave_ImportFrom(
        self, original_node: ImportFrom, updated_node: ImportFrom
    ) -> Union[
        BaseSmallStatement, FlattenSentinel[BaseSmallStatement], RemovalSentinel
    ]:
        if isinstance(updated_node.names, ImportStar):
            return updated_node

        names_to_keep = []
        module_name = get_absolute_module_from_package_for_import(None, updated_node)
        for name in updated_node.names:
            name_value = name.name.value
            found = False
            for import_item in self.import_items_to_be_removed:
                if (
                    import_item.module_name == module_name
                    and import_item.obj_name == name_value
                ):
                    found = True
                    break
            if not found:
                names_to_keep.append(name.with_changes(comma=MaybeSentinel.DEFAULT))

        if not names_to_keep:
            return RemoveFromParent()
        else:
            return updated_node.with_changes(names=names_to_keep)
