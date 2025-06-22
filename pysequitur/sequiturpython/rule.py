# Cython imports removed:
# import cython
# from .symbol cimport Symbol, Guard
# from .symbol import Symbol as PySymbol

# Standard Python imports:
from .symbol import Symbol, Guard # Assuming Guard is defined in symbol.py

# We need Grammar for grammar_instance.get_unique_rule_number()
# This import was commented out in the .pyx but is needed for Python.
# Assuming grammar.py now exists and is Python.
# from .grammar import Grammar # Removed to break circular import with grammar.py

class Rule(object):
    """docstring for Rule"""
    # Cython cdef public attributes become regular instance attributes
    # initialized in __init__.
    # Attributes guard, reference_count, unique_number

    def __init__(self, grammar_instance): # Type hint 'Grammar' removed
        super(Rule, self).__init__()
        # self.grammar_ref = grammar_instance # If we were to store it

        # Use Symbol.guard directly (it's a staticmethod)
        self.guard = Symbol.guard(grammar_instance, self)
        self.guard.join(self.guard)
        self.reference_count = 0

        self.unique_number = grammar_instance.get_unique_rule_number()

    def first(self): # Changed from cpdef Symbol to def
        # Removed <Guard> cast; direct attribute access
        return self.guard.next

    def last(self): # Changed from cpdef Symbol to def
        # Removed <Guard> cast
        return self.guard.prev

    def increment_reference_count(self): # Changed from cpdef int to def
        self.reference_count += 1
        return self.reference_count # Return for consistency if needed, though not strictly necessary

    def decrement_reference_count(self): # Changed from cpdef int to def
        self.reference_count -= 1
        return self.reference_count # Return for consistency

    def get_rule(self, rule_set): # 'rule_set' type hint 'list' removed for simplicity
        """docstring for get_rule"""
        # Removed cdef variable declarations
        symbol = self.first()
        output_array = []
        while not symbol.is_guard():
            output_array.append(symbol.get_rule(rule_set))
            symbol = symbol.next # Removed <Symbol> cast
        return output_array

    def print_rule(self, rule_set, output_array, line_length): # Type hints removed
        """docstring for print_rule"""
        # Removed cdef variable declaration
        symbol = self.first()
        while not symbol.is_guard():
            line_length = symbol.print_rule(rule_set, output_array, line_length)
            symbol = symbol.next # Removed <Symbol> cast
        return line_length

    def print_rule_expansion(self, rule_set, output_array, line_length): # Type hints removed
        """docstring for print_rule_expansion"""
        # Removed cdef variable declaration
        symbol = self.first()
        while not symbol.is_guard():
            line_length = symbol.print_rule_expansion(rule_set, output_array, line_length)
            symbol = symbol.next # Removed <Symbol> cast
        return line_length
