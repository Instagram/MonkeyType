from collections import defaultdict
from typing import (
    Dict,
    Set,
    Union,
    List,
    Tuple,
)

import libcst
from libcst import (
    Module,
    CSTTransformer,
    Import,
    BaseSmallStatement,
    RemovalSentinel,
    MaybeSentinel,
    RemoveFromParent,
    ImportFrom,
    FlattenSentinel,
    BaseCompoundStatement,
    SimpleStatementLine,
)
from libcst.codemod import (
    ContextAwareTransformer,
    CodemodContext,
)
from libcst.codemod.visitors import (
    AddImportsVisitor,
    ImportItem,
    GatherImportsVisitor,)
from libcst.helpers import get_absolute_module_from_package_for_import


class MoveImportsToTypeCheckingBlockVisitor(ContextAwareTransformer):
    CONTEXT_KEY = "MoveImportsToTypeCheckingBlockVisitor"

    def __init__(
        self,
        context: CodemodContext,
    ) -> None:
        super().__init__(context)

        self.object_mappings_to_be_moved = defaultdict(set)
        self.module_imports_to_be_moved = set()

    @staticmethod
    def store_imports_in_context(
        context: CodemodContext,
        object_mappings_to_be_moved: Dict[str, Set[str]],
        module_imports_to_be_moved: Set[str],
    ) -> None:
        context.scratch[MoveImportsToTypeCheckingBlockVisitor.CONTEXT_KEY] = (
            object_mappings_to_be_moved,
            module_imports_to_be_moved,
        )

    @staticmethod
    def _add_type_checking_import(source_module: Module) -> Module:
        context = CodemodContext()
        AddImportsVisitor.add_needed_import(context, "typing", "TYPE_CHECKING")
        transformer = AddImportsVisitor(context)
        transformed_source_module = transformer.transform_module(source_module)
        return transformed_source_module

    def _remove_imports(self, tree: Module) -> Module:
        transformer = RemoveImportsTransformer(
            self.object_mappings_to_be_moved,
            self.module_imports_to_be_moved
        )
        transformed_source_module = tree.visit(transformer)
        return transformed_source_module

    def _get_import_module(self):
        empty_code = libcst.parse_module("")
        context = CodemodContext()
        imports: List[ImportItem] = []
        for k, v_list in self.object_mappings_to_be_moved.items():
            for v in v_list:
                imports.append(ImportItem(k, v))

        for mod in self.module_imports_to_be_moved:
            imports.append(ImportItem(mod))

        context.scratch[AddImportsVisitor.CONTEXT_KEY] = imports
        transformer = AddImportsVisitor(context)
        transformed_source_module = transformer.transform_module(empty_code)

        return transformed_source_module

    @staticmethod
    def _replace_pass_with_imports(
        placeholder_module: Module,
        import_module: Module
    ) -> Module:
        return placeholder_module.with_deep_changes(
            old_node=placeholder_module.body[0].body,
            body=import_module.body,
        )

    def _split_module(
        self,
        module: Module
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
        if (
            not self.object_mappings_to_be_moved
            and not self.module_imports_to_be_moved
        ):
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
            (
                object_mappings_to_be_moved,
                module_imports_to_be_moved,
            ) = context_contents

            self.object_mappings_to_be_moved = object_mappings_to_be_moved
            self.module_imports_to_be_moved = module_imports_to_be_moved

            # Remove typing library since we do not want it
            # to be imported inside the if TYPE_CHECKING block
            self.object_mappings_to_be_moved.pop("typing", None)
            self.module_imports_to_be_moved.discard("typing")

            # Remove the newer imports since those are to be
            # shifted inside the if TYPE_CHECKING block
            tree = self._remove_imports(tree)

            # Add the new imports inside if TYPE_CHECKING block
            tree = self._add_if_type_checking_block(tree)

        return tree


class RemoveImportsTransformer(CSTTransformer):
    def __init__(
        self,
        import_objects_to_remove: Dict[str, Set[str]],
        import_modules_to_remove: Set[str],
    ) -> None:
        self.import_objects_to_remove = import_objects_to_remove
        self.import_modules_to_remove = import_modules_to_remove

    def leave_Import(
        self, original_node: Import, updated_node: Import
    ) -> Union[
        BaseSmallStatement, FlattenSentinel[BaseSmallStatement], RemovalSentinel
    ]:
        names_to_keep = []
        for name in updated_node.names:
            module_name = name.evaluated_name
            if module_name not in self.import_modules_to_remove:
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
        names_to_keep = []
        module_name = get_absolute_module_from_package_for_import(None, updated_node)
        for name in updated_node.names:
            name_value = name.name.value
            if name_value not in self.import_objects_to_remove.get(module_name, {}):
                names_to_keep.append(name.with_changes(comma=MaybeSentinel.DEFAULT))

        if not names_to_keep:
            return RemoveFromParent()
        else:
            return updated_node.with_changes(names=names_to_keep)
