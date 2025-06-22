import cython

# Forward declare Grammar and Rule if they are used as types here
# For now, assume they are 'object' or forward declared if methods return them.
# cdef class Grammar # from .grammar
# cdef class Rule    # from .rule

cdef class RuleIndex(int):
    pass # No C-level attributes or methods to declare beyond what int provides for now

cdef class Symbol(object):
    cdef public object grammar, next, prev
    # Declare methods that are cpdef or cdef and need to be called from other .pyx files
    cpdef hash_value(self)
    # Declare Python methods if they need to be callable on Symbol type from Cython
    # For 'def' methods, usually not needed in .pxd unless for specific override checks.
    # However, if other modules type a variable as 'Symbol' and call .value(), it should be here.
    cpdef object value(self) # Explicit object return
    cpdef object string_value(self) # Explicit object return
    cpdef bint is_guard(self) # Changed to cpdef and returns bint
    # Methods like join, insert_after, delete_digram, process_match etc.
    # are 'def' methods in the .pyx file. They are accessible via Python's lookup
    # and don't need to be in the .pxd for basic cimporting of the type itself,
    # unless they are part of a cpdef override chain or you need to call them
    # from C on a Symbol pointer and want static type checking.
    # For now, removing them from pxd for simplicity to get a clean compile.
    # def join(self, Symbol right)
    # def process_match(self, Symbol match)
    # def insert_after(self, Symbol symbol)

    # Static methods are not part of cdef class interface in .pxd for cimport
    # They are accessed via Python import of the module, e.g. symbol_module.Symbol.factory()
    # Or, if factory needs to be cimported, it would be a cdef function in the pxd.

cdef class Terminal(Symbol):
    cdef public object terminal # str
    cpdef delete(self)

cdef class NonTerminal(Symbol):
    cdef public object rule # Rule type
    cpdef delete(self)

cdef class Guard(Symbol):
    cdef public object rule # Rule type
    # Guard.delete() is different, it doesn't call self.delete_digram()
    # It just does self.prev.join(self.next). So it can be cpdef too.
    cpdef delete(self)

# If Symbol.factory and Symbol.guard are to be cimported as functions:
# cdef Symbol factory(object grammar, object value)
# cdef Guard guard(object grammar, object rule_instance)
# But this requires them to be cdef functions in symbol.pyx, not staticmethods on the class.
# For now, will rely on Python import for factory/guard.
