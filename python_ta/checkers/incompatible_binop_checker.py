"""
"""
import astroid

from pylint.interfaces import IAstroidChecker
from pylint.checkers import BaseChecker
from pylint.checkers.utils import check_messages


class IncompatibleBinOp(BaseChecker):

    __implements__ = IAstroidChecker

    name = 'incompatible-binop'

    msgs = {'E1234': ('Incompatible binary operation.'
                     , 'incompatible-binop'
                     , 'ERROR MESSAGE HERE')}

    # this is important so that your checker is executed before others
    priority = -1

    def _incompatible_binop_operation(self, node):
        """
        """
        node

    @check_messages("incompatible-binop")
    def visit_binop(self, node):
        if self._incompatible_binop_operation(node):
            self.add_message('incompatible_binop', node=node)


def register(linter):
    """required method to auto register this checker"""
    linter.register_checker(IncompatibleBinOp(linter))
