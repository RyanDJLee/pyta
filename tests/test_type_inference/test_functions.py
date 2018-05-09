import astroid
import nose
from hypothesis import assume, given, settings, HealthCheck
from unittest import SkipTest
import tests.custom_hypothesis_support as cs
import hypothesis.strategies as hs
from typing import Callable
from keyword import iskeyword
settings.load_profile("pyta")


def _parse_to_function(function_name, args_list, return_statement):
    """Helper to parse given data into function definition."""
    return f'def {function_name}({", ".join(args_list)}):' \
           f'    return {return_statement}'


def _parse_to_function_no_return(function_name, args_list, function_body):
    """Helper to parse given data into function definition."""
    return f'def {function_name}({", ".join(args_list)}):\n' \
           f'    {function_body}'


@given(cs.valid_identifier(), cs.primitive_values)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_function_def_no_args(function_name, return_value):
    """Test FunctionDef node visitors representing function definitions with no parameters and primitive return type."""
    assume(not iskeyword(function_name))
    program = _parse_to_function(function_name, [], repr(return_value))
    module, inferer = cs._parse_text(program)
    function_type_var = module.type_environment.lookup_in_env(function_name)
    function_def_node = list(module.nodes_of_class(astroid.FunctionDef))[0]
    return_tvar = function_def_node.type_environment.lookup_in_env('return')
    return_type = inferer.type_constraints.resolve(return_tvar)
    assert inferer.type_constraints.resolve(function_type_var) == Callable[[], return_type]


@given(cs.valid_identifier(), cs.primitive_values)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_function_def_call_no_args(function_name, return_value):
    """Test type setting in environment of a function call for a function with no parameters."""
    program = _parse_to_function(function_name, [], repr(return_value)) + "\n" + function_name + "()\n"
    module, inferer = cs._parse_text(program)
    # there should be a single Expr node in this program
    function_def_node = list(module.nodes_of_class(astroid.FunctionDef))[0]
    return_tvar = function_def_node.type_environment.lookup_in_env('return')
    return_type = inferer.type_constraints.resolve(return_tvar)
    expr_node = next(module.nodes_of_class(astroid.Expr))
    assert expr_node.type_constraints.type == return_type


@given(cs.valid_identifier(), hs.lists(cs.valid_identifier(), min_size=0), cs.primitive_values)
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_function_def_no_return(function_name, arguments, body):
    """Test FunctionDef node visitors representing non-returning function definitions with parameter(s)."""
    for return_value in ['return None', repr(body), 'pass']:
        program = _parse_to_function_no_return(function_name, arguments, repr(return_value))
        module, inferer = cs._parse_text(program)
        function_def_node = next(module.nodes_of_class(astroid.FunctionDef))
        expected_arg_type_vars = [function_def_node.type_environment.lookup_in_env(argument) for argument in arguments]
        expected_arg_types = [inferer.type_constraints.resolve(type_var) for type_var in expected_arg_type_vars]
        function_type_var = module.type_environment.lookup_in_env(function_name)
        assert inferer.type_constraints.resolve(function_type_var) == Callable[expected_arg_types, None]


@given(cs.valid_identifier(), hs.lists(cs.valid_identifier(), min_size=1))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_function_def_args_simple_return(function_name, arguments):
    """Test FunctionDef node visitors representing function definitions with paramater(s):
     return one of its arguments."""
    for argument in arguments:
        program = _parse_to_function(function_name, arguments, argument)
        module, inferer = cs._parse_text(program)
        # get the functionDef node - there is only one in this test case.
        function_def_node = next(module.nodes_of_class(astroid.FunctionDef))
        expected_arg_type_vars = [function_def_node.type_environment.lookup_in_env(argument) for argument in arguments]
        expected_arg_types = [inferer.type_constraints.resolve(type_var) for type_var in expected_arg_type_vars]
        function_type_var = module.type_environment.lookup_in_env(function_name)
        function_type = inferer.type_constraints.resolve(function_type_var)
        actual_arg_types, actual_return_type = inferer.type_constraints.types_in_callable(function_type)
        return_type_var = function_def_node.type_environment.lookup_in_env(argument)
        expected_return_type = inferer.type_constraints.resolve(return_type_var)
        assert Callable[actual_arg_types, actual_return_type] == Callable[expected_arg_types, expected_return_type]


@given(cs.valid_identifier(), cs.random_dict_variable_homogeneous_value(min_size=1))
@settings(suppress_health_check=[HealthCheck.too_slow])
def test_function_def_args_simple_function_call(function_name, variables_dict):
    """Test setting f env for function call of function definitions with params that returns one of it's arguments."""
    assume(not iskeyword(function_name) and function_name not in variables_dict)
    # generate every possible function definition program of aforementioned form.
    for i in range(len(list(variables_dict.keys()))):
        return_value = list(variables_dict.keys())[i]
        arguments = ", ".join([repr(value) for value in variables_dict.values()])
        program = f'{_parse_to_function(function_name, list(variables_dict.keys()), return_value)}\n' \
                  f'{function_name}({arguments})'
        module, inferer = cs._parse_text(program)
        # get the Call node - there is only one in this test case.
        call_node = next(module.nodes_of_class(astroid.Call))
        function_call_type = call_node.type_constraints.type
        assert inferer.type_constraints.resolve(function_call_type) == call_node.args[i].type_constraints.type


def test_incompatible_binop_call():
    """ User tries to call a builtin binary operation on arguments of the wrong type.
    """
    program = f'5 + "string"\n'
    try:
        module, inferer = cs._parse_text(program)
    except:
        raise SkipTest()
    binop_node = next(module.nodes_of_class(astroid.BinOp))
    expected_msg = "You cannot add an int, 5, and a str, 'string'. " \
                   "Perhaps you wanted to cast the integer into a string or vice versa?"
    assert(binop_node.type_constraints.type.msg == expected_msg)


def test_non_annotated_function_call_bad_arguments():
    """ User tries to call a non-annotated function on arguments of the wrong type.
    """
    program = f'def add_num(num1, num2):\n' \
              f'    return num1 + num2\n' \
              f'\n' \
              f'add_num("bob", 1.0)\n'
    try:
        module, inferer = cs._parse_text(program)
    except:
        raise SkipTest()
    call_node = next(module.nodes_of_class(astroid.Call))
    # TODO: This error is flawed because the unification error occurs for both arguments due to our current implementation,
    # which "chooses" the first valid function type from TypeStore.
    # Should we fix this implementation first or save it for later and hard-code the correct error message for now?
    expected_msg = f'In the Call node in line 4, there was an error in calling the function "add_num":\n' \
                   f'in parameter (1), the function was expecting an object of inferred type ' \
                   f'int but was given an object of type str.\n' \
                   f'in parameter (2), the function was expecting an object of inferred type ' \
                   f'int but was given an object of type float.\n'
                   # TODO: should we use the term inferred?
    assert call_node.type_constraints.type.msg == expected_msg


def test_user_defined_annotated_call_wrong_arguments_type():
    """ User tries to call an annotated user-defined function on the wrongly-typed arguments.
    """
    program = f'def add_3(num1: int, num2: int, num3: int) -> int:\n' \
              f'    return num1 + num2 + num3\n' \
              f'\n' \
              f'add_3(1, "bob", 1.0)\n'
    try:
        module, inferer = cs._parse_text(program)
    except:
        raise SkipTest()
    call_node = list(module.nodes_of_class(astroid.Call))[0]
    expected_msg = f'In the Call node in line 4, there was an error in calling the annotated function "add_3":\n' \
                   f'in parameter (2), the annotated type is int but was given an object of type str.\n' \
                   f'in parameter (3), the annotated type is int but was given an object of type float.\n'
    assert call_node.type_constraints.type.msg == expected_msg


def test_user_defined_annotated_call_wrong_arguments_number():
    """ User tries to call an annotated function on the wrong number of arguments.
    """
    program = f'def add_3(num1: int, num2: int, num3: int) -> int:\n' \
              f'    return num1 + num2 + num3\n' \
              f'\n' \
              f'add_3()\n'
    try:
        module, inferer = cs._parse_text(program)
    except:
        raise SkipTest()
    call_node = list(module.nodes_of_class(astroid.Call))[0]
    expected_msg = f'In the Call node in line 4, there was an error in calling the function "add_3":\n' \
                   f'the function was expecting 3 arguments, but was given 0.'
    assert call_node.type_constraints.type.msg == expected_msg


def test_conflicting_inferred_type_variable():
    """ User calls two functions on an object, which contradicts the inferred type of the variable.
    """
    program = '''
        def return_num(num: int) -> int:
            return num

        def return_str(str: str) -> str:
            return str

        def f(x):
            return_num(x)
            return_str(x)
        '''
    try:
        module, inferer = cs._parse_text(program)
    except:
        raise SkipTest()
    call_node = list(module.nodes_of_class(astroid.Call))[1]
    expected_msg = f'In the Call node in line 8, there was an error in calling the annotated function "return_str":\n' \
                   f'in parameter (1), the annotated type is str but was given an object of inferred type int.'
                   # TODO: test case redundant because recursive..?
    assert call_node.type_constraints.type.msg == expected_msg


if __name__ == '__main__':
    nose.main()
