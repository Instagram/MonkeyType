# Copyright (c) 2017-present, Facebook, Inc.
# All rights reserved.
#
# This source code is licensed under the BSD-style license found in the
# LICENSE file in the root directory of this source tree.
from typing import Type, List

from libcst.codemod import CodemodTest, Codemod, CodemodContext
from libcst.codemod.visitors import ImportItem

from monkeytype.type_checking_imports_transformer import (
    MoveImportsToTypeCheckingBlockVisitor,
)


class TestMoveImportsToTypeCheckingBlockVisitor(CodemodTest):

    TRANSFORM: Type[Codemod] = MoveImportsToTypeCheckingBlockVisitor

    def run_test_case(
        self,
        import_items_to_be_moved: List[ImportItem],
        before: str,
        after: str,
    ) -> None:
        context = CodemodContext()
        MoveImportsToTypeCheckingBlockVisitor.store_imports_in_context(
            context,
            import_items_to_be_moved,
        )
        self.assertCodemod(before, after, context_override=context)

    def test_simple_add_type_checking(self):
        source = """
            from __future__ import annotations

            from a import B
            import c.C
        """
        import_items_to_be_moved = [
            ImportItem("a", "B"),
            ImportItem("c.C"),
        ]
        expected = """
            from __future__ import annotations
            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                import c.C
                from a import B
        """

        self.run_test_case(import_items_to_be_moved, source, expected)

    def test_type_checking_block_already_exists(self):
        source = """
            from __future__ import annotations

            from typing import TYPE_CHECKING

            from a import B
            import c.C

            if TYPE_CHECKING:
                from d import E
        """
        import_items_to_be_moved = [
            ImportItem("a", "B"),
            ImportItem("c.C"),
        ]
        expected = """
            from __future__ import annotations

            from typing import TYPE_CHECKING

            if TYPE_CHECKING:
                import c.C
                from a import B

            if TYPE_CHECKING:
                from d import E
        """

        self.run_test_case(import_items_to_be_moved, source, expected)

    def test_typing_imports(self):
        source = """
            from __future__ import annotations

            from typing import List

            from a import B
        """
        import_items_to_be_moved = [
            ImportItem("typing", "List"),
            ImportItem("a", "B"),
        ]
        expected = """
            from __future__ import annotations

            from typing import TYPE_CHECKING, List

            if TYPE_CHECKING:
                from a import B
        """

        self.run_test_case(import_items_to_be_moved, source, expected)

    def test_move_imports__mix(self):
        source = """
            from __future__ import annotations
            from __future__ import division

            from typing import Dict, List, TYPE_CHECKING

            import e
            from a import (
                B,
                C,
                D,
            )
            from f import G
            from h import (
                I,
                J,
            )
            from n import *

            if TYPE_CHECKING:
                from k import L, M

            def func():
                pass
        """
        import_items_to_be_moved = [
            ImportItem("a", "B"),
            ImportItem("a", "C"),
            ImportItem("e"),
            ImportItem("h", "I"),
            ImportItem("typing", "List"),
            ImportItem("typing", "Dict"),
        ]
        expected = """
            from __future__ import annotations
            from __future__ import division

            from typing import Dict, List, TYPE_CHECKING
            from a import (
                D)
            from f import G
            from h import (
                J)
            from n import *

            if TYPE_CHECKING:
                import e
                from a import B, C
                from h import I

            if TYPE_CHECKING:
                from k import L, M

            def func():
                pass
        """

        self.run_test_case(import_items_to_be_moved, source, expected)
