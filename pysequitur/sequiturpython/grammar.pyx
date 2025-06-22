import cython
from .symbol cimport Symbol, RuleIndex # Assuming RuleIndex is cdef class in symbol.pyx
from .symbol import Symbol as PySymbol # For static methods like factory
# Forward declaration for Rule, assuming it will be a cdef class in rule.pyx
# If rule.pxd exists and defines Rule, that would be better.
# For now, we'll rely on Python imports for Rule if cimport fails early,
# or define Rule as "cdef class Rule" here if it were simple enough.
# Best approach is to cimport it once rule.pyx and a potential rule.pxd are set up.
from .rule cimport Rule # Changed to cimport

cdef class Grammar(object):
    """docstring for Grammar"""

    # For class-level attributes not part of an instance's __dict__
    # and if you want C-level static members (less common for Python-interfacing classes unless for pure C speed)
    # Python's class attributes work fine mostly.
    # If unique_rule_number is meant to be a C integer:
    # cdef public static int unique_rule_number = 1
    # Otherwise, as a Python object (int):
    unique_rule_number = 1 # Standard Python class attribute

    cdef public dict digram_index
    cdef public object root_production # Will be type Rule

    def __init__(self):
        super(Grammar, self).__init__()
        self.digram_index = {}
        # When Rule is cimported: self.root_production = <Rule>Rule(self)
        self.root_production = Rule(self)

    def train_string(self, str input_sequence): # Type hint for input_sequence
        """docstring for train_string"""
        cdef int i = 0
        cdef int l = len(input_sequence)
        cdef Symbol last_symbol_in_prod, new_sym
        cdef Symbol match # Stores result of get_index

        if i < l:
            # Assuming self.root_production is Rule, and last() returns Symbol
            last_symbol_in_prod = (<Rule>self.root_production).last()
            new_sym = PySymbol.factory(self, input_sequence[i]) # Use PySymbol
            last_symbol_in_prod.insert_after(new_sym)
            i += 1
        while i < l:
            last_symbol_in_prod = (<Rule>self.root_production).last()
            new_sym = PySymbol.factory(self, input_sequence[i]) # Use PySymbol
            last_symbol_in_prod.insert_after(new_sym)
            i += 1

            # last().prev should be a Symbol
            match = self.get_index((<Symbol>(<Rule>self.root_production).last()).prev)
            if not match:
                self.add_index((<Symbol>(<Rule>self.root_production).last()).prev)
            # Ensure match.next and the other symbol are comparable
            elif (<Symbol>match).next != (<Symbol>(<Rule>self.root_production).last()).prev:
                (<Symbol>((<Symbol>(<Rule>self.root_production).last()).prev)).process_match(match)


    def add_index(self, Symbol digram):
        """docstring for index"""
        self.digram_index[digram.hash_value()] = digram

    def get_index(self, Symbol digram):
        """docstring for get"""
        # hash_value() is cpdef, callable from Cython
        return self.digram_index.get(digram.hash_value())

    def clear_index(self, Symbol digram):
        """docstring for clear_index"""
        if self.digram_index.get(digram.hash_value()) == digram:
            self.digram_index[digram.hash_value()] = None

    def print_grammar(self):
        """docstring for print_grammar"""
        cdef list output_array = []
        # Rule will be cimported later
        cdef list rule_set = [<Rule>self.root_production]
        cdef int i = 0
        cdef Rule current_rule
        cdef int line_length

        for current_rule in rule_set:
            output_array.append("%s --(%d)--> " % (i, current_rule.reference_count))
            # Assuming print_rule and print_rule_expansion are methods of Rule
            line_length = current_rule.print_rule(rule_set, output_array, len("%s --(%d)--> " % (i, current_rule.reference_count)))
            if i > 0:
                output_array.append(' ' * (57 - line_length))
                line_length = current_rule.print_rule_expansion(rule_set, output_array, line_length)
            output_array.append('\n');
            i += 1
        return "".join(output_array)

    def get_grammar(self):
        """docstring for get_grammar"""
        cdef list rule_set = [<Rule>self.root_production]
        cdef Rule r
        # This will create a list of Python objects (results of get_rule)
        cdef list result_list = []
        for r in rule_set:
            result_list.append(r.get_rule(rule_set))
        return result_list

    @classmethod
    def get_unique_rule_number(cls):
        num = cls.unique_rule_number
        cls.unique_rule_number += 1
        return num
