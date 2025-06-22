import cython
from .symbol cimport Symbol # Assuming Symbol.pxd exists and is correct

# Forward declare Grammar if it's used as a type for constructor or attributes
# cdef class Grammar # from .grammar

cdef class Rule(object):
    cdef public Symbol guard # Actually a Guard instance
    cdef public int reference_count
    cdef public int unique_number
    # cdef public object grammar_ref # If you store grammar instance

    # Constructor signature if needed for cinit
    # def __init__(self, object grammar_instance) # Using object for grammar_instance for now

    cpdef Symbol first(self)
    cpdef Symbol last(self)
    cpdef int increment_reference_count(self)
    cpdef int decrement_reference_count(self)

    # Python methods (def) if they need to be called from other Cython modules
    # on a variable typed as 'Rule'.
    # Removing these 'def' methods from pxd for now to simplify initial compilation.
    # def get_rule(self, list rule_set)
    # def print_rule(self, list rule_set, list output_array, int line_length)
    # def print_rule_expansion(self, list rule_set, list output_array, int line_length)
