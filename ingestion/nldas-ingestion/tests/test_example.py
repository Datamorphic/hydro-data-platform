
"""
`unit test`: tests 1 unit (function, method, etc) of code for expected behavior.

`Patch/Monkey Patch`: Replaces code functionality at runtime to intentionally bypass behavior. For example, replacing
    a networking call with a currated response that can be tested against. The goal is to overwrite code.

`Mock/Mocking`: Replaces code dependencies with controlled test doubles. The goal is to create a fake object to simulate
    behavior instead of overwrite the programs code.

`Fixtures`: Stored procedural logic that is used during tests to help with setup/teardown to reduce repeating syntax.

Where to patch? `The rule of thumb is`: You must patch the name ***where it is looked up***, not where it is defined.
    If the thing being tested is class or function from another module, say module1.function1, that imports a function or class from
    another module, say module2.function2 and calls it, say function1 -calls-> function2, then when we import module1 into our test
    script, we need to patch "module1.function2" not "module2.function2" because "module1.function1" knows the function as such.
"""

import pytest

# NOTE: pytest performs dependency injection at runtime
# whereby it looks at the scripts registry of fixtures for one named `service`, 
# then it call it `service()`, which returns an int of 1 in this case, and then passes the result to the test function `test_service(service())` == `test_service(1)`

class thing:
    @staticmethod
    def do(x: int) -> int:
        return x + 1

@pytest.fixture
def service() -> int:
    return int(1)

def test_service(service: int):
    number = service
    print(f"The number is {number}")

def test_thing_do_mocker(mocker):
    mock_do = mocker.patch("test_example.thing.do") # must call <module>.<object | function>.<sub-object | method | attribute | property>.<sub-object | method | attribute | property> relative to where it is called. PATCH WHERE IT IS LOOKED UP

    mock_do.return_value = 2

    result = thing.do(1)
    mock_do.assert_called_with(1)
    assert result != 1