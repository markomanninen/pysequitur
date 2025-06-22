import cython
# cimport Guard, but also Symbol as Guard is a Symbol.
from .symbol cimport Symbol, Guard
from .symbol import Symbol as PySymbol # For static methods like guard
# We need to import Grammar to call its class method, or pass grammar instance
# For now, assume grammar instance is passed and has get_unique_rule_number
# from .grammar cimport Grammar # If Grammar methods are directly called on class

cdef class Rule(object):
    """docstring for Rule"""
    # Attributes are defined in rule.pxd
    # cdef public Symbol guard
    # cdef public int reference_count
    # cdef public int unique_number
    # cdef public object grammar_ref

    def __init__(self, grammar_instance): # grammar_instance will be of type Grammar
        super(Rule, self).__init__()
        # Store grammar_instance if needed for other methods, or just use for init
        # self.grammar_ref = grammar_instance

        # Symbol.guard returns a Guard instance, which is a Symbol
        self.guard = PySymbol.guard(grammar_instance, self) # Use PySymbol
        self.guard.join(self.guard) # Guard's join method
        self.reference_count = 0

        # Access unique_number via the passed grammar_instance
        # This assumes Grammar class in grammar.pyx has get_unique_rule_number method
        self.unique_number = grammar_instance.get_unique_rule_number()


    cpdef Symbol first(self): # cpdef for potential C-level access if faster
        return (<Guard>self.guard).next # Cast guard to Guard if needed, then access Symbol methods

    cpdef Symbol last(self): # cpdef
        return (<Guard>self.guard).prev

    cpdef int increment_reference_count(self): # cpdef
        self.reference_count += 1
        return self.reference_count

    cpdef int decrement_reference_count(self): # cpdef
        self.reference_count -= 1
        return self.reference_count

    def get_rule(self, rule_set): # rule_set is a list
        """docstring for get_rule"""
        cdef Symbol symbol = self.first()
        cdef list output_array = []
        while not symbol.is_guard(): # is_guard is a method of Symbol
            output_array.append(symbol.get_rule(rule_set)) # get_rule is method of Symbol
            symbol = (<Symbol>symbol).next # Cast to Symbol to access .next
        return output_array

    def print_rule(self, rule_set, output_array, int line_length): # rule_set, output_array are lists
        """docstring for print_rule"""
        cdef Symbol symbol = self.first()
        while not symbol.is_guard():
            line_length = symbol.print_rule(rule_set, output_array, line_length) # print_rule is method of Symbol
            symbol = (<Symbol>symbol).next
        return line_length

    def print_rule_expansion(self, rule_set, output_array, int line_length): # rule_set, output_array are lists
        """docstring for print_rule_expansion"""
        cdef Symbol symbol = self.first()
        while not symbol.is_guard():
            line_length = symbol.print_rule_expansion(rule_set, output_array, line_length) # print_rule_expansion is method of Symbol
            symbol = (<Symbol>symbol).next
        return line_length
