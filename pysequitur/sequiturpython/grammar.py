# Cython imports removed:
# import cython
# from .symbol cimport Symbol, RuleIndex
# from .symbol import Symbol as PySymbol
# from .rule cimport Rule

# Standard Python imports:
from .symbol import Symbol, RuleIndex
from .rule import Rule

class Grammar(object):
    """docstring for Grammar"""

    unique_rule_number = 1 # Standard Python class attribute

    # Cython cdef public attributes become regular instance attributes
    # initialized in __init__
    # cdef public dict digram_index
    # cdef public object root_production

    def __init__(self):
        super(Grammar, self).__init__()
        self.digram_index = {}
        self.root_production = Rule(self) # Rule() is now standard Python class constructor

    def train_string(self, input_sequence): # Removed 'str' type hint
        """docstring for train_string"""
        # Removed cdef variable declarations
        i = 0
        l = len(input_sequence)
        # last_symbol_in_prod, new_sym, match will be dynamically typed

        if i < l:
            last_symbol_in_prod = self.root_production.last() # No <Rule> cast
            # Use Symbol.factory directly, assuming Symbol is the imported class
            new_sym = Symbol.factory(self, input_sequence[i])
            last_symbol_in_prod.insert_after(new_sym)
            i += 1
        while i < l:
            last_symbol_in_prod = self.root_production.last() # No <Rule> cast
            new_sym = Symbol.factory(self, input_sequence[i]) # Use Symbol.factory
            last_symbol_in_prod.insert_after(new_sym)
            i += 1

            # Removed <Symbol> and <Rule> casts
            match = self.get_index(self.root_production.last().prev)
            if not match:
                self.add_index(self.root_production.last().prev)
            elif match.next != self.root_production.last().prev:
                self.root_production.last().prev.process_match(match)

    def add_index(self, digram): # Removed 'Symbol' type hint
        """docstring for index"""
        self.digram_index[digram.hash_value()] = digram

    def get_index(self, digram): # Removed 'Symbol' type hint
        """docstring for get"""
        return self.digram_index.get(digram.hash_value())

    def clear_index(self, digram): # Removed 'Symbol' type hint
        """docstring for clear_index"""
        if self.digram_index.get(digram.hash_value()) == digram:
            self.digram_index[digram.hash_value()] = None # No need to use Py_None

    def print_grammar(self):
        """docstring for print_grammar"""
        # Removed cdef variable declarations
        output_array = []
        rule_set = [self.root_production] # No <Rule> cast
        i = 0
        # current_rule, line_length dynamically typed

        for current_rule in rule_set: # current_rule is Rule instance
            output_array.append("%s --(%d)--> " % (i, current_rule.reference_count))
            line_length = current_rule.print_rule(rule_set, output_array, len("%s --(%d)--> " % (i, current_rule.reference_count)))
            if i > 0:
                output_array.append(' ' * (57 - line_length))
                line_length = current_rule.print_rule_expansion(rule_set, output_array, line_length)
            output_array.append('\n');
            i += 1
        return "".join(output_array)

    def get_grammar(self):
        """docstring for get_grammar"""
        # Removed cdef variable declarations
        rule_set = [self.root_production] # No <Rule> cast
        # r is dynamically typed
        result_list = []
        for r_item in rule_set: # Renamed r to r_item to avoid confusion if r was a cdef type
            result_list.append(r_item.get_rule(rule_set))
        return result_list

    @classmethod
    def get_unique_rule_number(cls):
        num = cls.unique_rule_number
        cls.unique_rule_number += 1
        return num
