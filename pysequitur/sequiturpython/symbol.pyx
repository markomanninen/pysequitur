import cython
# For access to staticmethods within the same file if methods are called on cimported types
from .symbol import Symbol as PySymbol
# cimports must be at module level
from .rule cimport Rule

# Few constants for presentation logics
RULE_INDEX_STR = "^%s"

# Making RuleIndex a cdef class as it's simple and used in typing
cdef class RuleIndex(int):
    """
    Reason to use separate class for rule index values is that
    they must be separated from possible numerical sequence values
    """
    def __repr__(self):
        return RULE_INDEX_STR % self

cdef class Symbol(object):
    """docstring for Symbol"""
    # Attributes grammar, next, prev are defined in symbol.pxd
    # cdef public object grammar, next, prev
    # 'rule' and 'terminal' are specific to subclasses, defined there for clarity

    # This is the base implementation for cpdef method declared in pxd
    cpdef object value(self):
        raise NotImplementedError("This method should be overridden in subclasses")

    def __init__(self, grammar): # Type of grammar will be Grammar later
        """docstring for __init__"""
        self.grammar = grammar
        self.next = None
        self.prev = None

    def print_terminal(self):
        """docstring for print_terminal"""
        return self.value()

    def print_rule_expansion(self, _, output_array, line_length):
        """docstring for print_rule_expansion"""
        output_array.append(self.print_terminal())
        return line_length + len(self.print_terminal())

    def print_rule(self, _, output_array, line_length):
        """docstring for print_rule"""
        output_array.append("%s " % self.print_terminal())
        return line_length + len("%s " % self.print_terminal())

    def get_rule(self, _):
        """docstring for print_rule"""
        return self.print_terminal()

    @staticmethod
    def factory(grammar, value): # Type of grammar will be Grammar, value can be varied
        """docstring for factory"""
        # from .rule cimport Rule # Moved to module level

        if isinstance(value, str):
            return Terminal(grammar, value)
        elif isinstance(value, Terminal): # value here is Symbol type
            return Terminal(grammar, (<Terminal>value).terminal) # Cast to access .terminal
        elif isinstance(value, NonTerminal): # value here is Symbol type
            return NonTerminal(grammar, (<NonTerminal>value).rule) # Cast to access .rule
        elif isinstance(value, Rule): # value here is Rule type
            return NonTerminal(grammar, value)
        else:
            # Consider raising TypeError for better Python integration
            raise TypeError("type(value) == %s" % type(value))


    @staticmethod
    def guard(grammar, value): # Type of grammar will be Grammar, value will be Rule
        """docstring for guard"""
        return Guard(grammar, value)

    def join(self, Symbol right):
        """
        Links two symbols together, removing any old digram from the hash table.
        """
        if self.next:
            self.delete_digram()

            if ((right.prev is not None) and (right.next is not None) and
                right.value() == (<Symbol>right.prev).value() and # Cast for .value()
                right.value() == (<Symbol>right.next).value()):  # Cast for .value()
                self.grammar.add_index(right)
            if ((self.prev is not None) and (self.next is not None) and
                self.value() == (<Symbol>self.next).value() and # Cast for .value()
                self.value() == (<Symbol>self.prev).value()):  # Cast for .value()
                self.grammar.add_index(self)
        self.next = right
        right.prev = self

    def delete_digram(self):
        """Removes the digram from the hash table"""
        if self.is_guard() or (<Symbol>self.next).is_guard(): # Cast for .is_guard()
            pass
        else:
            self.grammar.clear_index(self)

    def insert_after(self, Symbol symbol):
        """Inserts a symbol after this one"""
        symbol.join(self.next)
        self.join(symbol)

    cpdef bint is_guard(self): return False # Overridden by Guard class

    def expand(self):
        """
        This symbol is the last reference to its rule. It is deleted, and the
        contents of the rule substituted in its place.
        """
        cdef Symbol left, right, first, last
        left = <Symbol>self.prev
        right = <Symbol>self.next
        # Assuming self is NonTerminal, so self.rule exists.
        first = (<NonTerminal>self).rule.first()
        last = (<NonTerminal>self).rule.last()

        self.grammar.clear_index(self) # clear_index for self (a NonTerminal)
        left.join(first)
        last.join(right)
        self.grammar.add_index(last)

    def propagate_change(self):
        """docstring for propagate_change"""
        cdef Symbol match
        if self.is_guard() or (<Symbol>self.next).is_guard(): # Cast
            if ((<Symbol>self.next).is_guard() or (<Symbol>(<Symbol>self.next).next).is_guard()): # Casts
                return
            match = self.grammar.get_index(self.next)
            if not match:
                self.grammar.add_index(self.next)
            elif match.next != self.next:
                (<Symbol>self.next).process_match(match) # Cast
        else:
            match = self.grammar.get_index(self)
            if not match:
                self.grammar.add_index(self)
                if ((<Symbol>self.next).is_guard() or (<Symbol>(<Symbol>self.next).next).is_guard()): # Casts
                    return
                match = self.grammar.get_index(self.next)
                if not match:
                    self.grammar.add_index(self.next)
                elif match.next != self.next:
                    (<Symbol>self.next).process_match(match) # Cast
            elif match.next != self:
                self.process_match(match)


    def substitute(self, rule_obj): # Renamed from rule to rule_obj to avoid conflict if Rule class is cimported
        """Replace a digram with a non-terminal"""
        # rule_obj will be type Rule
        cdef Symbol prev_sym
        prev_sym = <Symbol>self.prev
        # Ensure delete is cpdef and called correctly
        (<Symbol>prev_sym.next).delete()
        (<Symbol>prev_sym.next).delete()
        prev_sym.insert_after(PySymbol.factory(self.grammar, rule_obj)) # Use PySymbol

    def process_match(self, Symbol match):
        """Deal with a matching digram"""
        # from .rule cimport Rule # Moved to module level
        cdef object rule_obj # Will be type Rule

        # Need to cast match.prev and match.next.next
        if (<Symbol>match.prev).is_guard() and (<Symbol>(<Symbol>match.next).next).is_guard():
            # reuse an existing rule
            rule_obj = (<Guard>match.prev).rule # Cast to Guard to access .rule
            self.substitute(rule_obj)
            (<Symbol>self.prev).propagate_change() # Cast
        else:
            # create a new rule
            rule_obj = Rule(self.grammar)
            rule_obj.last().insert_after(PySymbol.factory(self.grammar, self)) # Use PySymbol
            rule_obj.last().insert_after(PySymbol.factory(self.grammar, self.next)) # Use PySymbol
            self.grammar.add_index(rule_obj.first())

            match.substitute(rule_obj)
            (<Symbol>match.prev).propagate_change() # Cast
            self.substitute(rule_obj)
            (<Symbol>self.prev).propagate_change() # Cast

        # Check for an under-used rule
        # Need to cast rule_obj.first() to NonTerminal to access .rule
        if NonTerminal == type(rule_obj.first()) and (<NonTerminal>rule_obj.first()).rule.reference_count == 1:
            (<NonTerminal>rule_obj.first()).expand()

    def value(self):
        """docstring for value"""
        # This method is overridden in subclasses, this base version might not be directly called
        # if all instances are of type Terminal, NonTerminal, or Guard.
        # If it can be called on a base Symbol instance (if any created), it needs definition.
        # For now, assuming it's overridden. If Symbol instances are directly made, this needs thought.
        # Defaulting to a placeholder or error if not overridden by a concrete type.
        # However, `self.rule` is not a member of Symbol base, but NonTerminal/Guard.
        # `self.terminal` is not a member of Symbol base, but Terminal.
        # This implies `value()` MUST be called on a subclass instance.
        # Cython might require this to be more explicit or for Symbol to be @abstract.
        # For now, let it be, relying on Python's dynamic dispatch.
        # To make Cython happier if direct Symbol calls to value() were possible and unspecific:
        # raise NotImplementedError("value() must be called on a subclass like Terminal or NonTerminal")
        # It's better to make it abstract or ensure it's always overridden.
        # For cpdef, it needs a C return type if not object. Assuming object for now.
        # If it's truly abstract, this body should raise NotImplementedError.
        raise NotImplementedError("This method should be overridden in subclasses")

    cpdef object string_value(self): # Added object return type
        """docstring for string_value"""
        # Similar to value(), this is typically called on subclass instances.
        # Overridden in Terminal, NonTerminal, Guard.
        raise NotImplementedError("This method should be overridden in subclasses")

    cpdef hash_value(self): # Made cpdef as requested
        """docstring for hash_value"""
        # Assuming self.next is Symbol, so string_value can be called.
        # If self.next could be None (e.g. end of a list), this needs a check.
        # The original python code implies .next is always a Symbol (often a Guard).
        return (self.string_value(), (<Symbol>self.next).string_value()) # Cast self.next

cdef class Terminal(Symbol):
    """docstring for Terminal"""
    # Attribute terminal is defined in symbol.pxd
    # cdef public object terminal

    def __init__(self, grammar, terminal_value): # terminal_value should be str
        super(Terminal, self).__init__(grammar)
        self.terminal = terminal_value

    cpdef object value(self): # Added object return type, changed to cpdef
        """docstring for value"""
        return self.terminal

    cpdef object string_value(self): # Added object return type, changed to cpdef
        return self.terminal

    cpdef delete(self): # Changed to cpdef
        """
        Cleans up for symbol deletion: removes hash table entry and decrements
        rule reference count.
        """
        (<Symbol>self.prev).join(self.next) # Cast
        self.delete_digram()

cdef class NonTerminal(Symbol):
    """docstring for NonTerminal"""
    # Attribute rule is defined in symbol.pxd
    # cdef public object rule

    def __init__(self, grammar, rule_obj): # rule_obj should be Rule type
        super(NonTerminal, self).__init__(grammar)
        self.rule = rule_obj
        self.rule.increment_reference_count()

    cpdef object value(self): # Added object return type, changed to cpdef
        """docstring for value"""
        return RuleIndex(self.rule.unique_number)

    cpdef object string_value(self): # Added object return type, changed to cpdef
        """docstring for string_value"""
        return "rule(%d)" % self.rule.unique_number

    def print_rule(self, rule_set, output_array, line_length):
        """docstring for print_rule"""
        if self.rule in rule_set:
            rule_index = rule_set.index(self.rule)
        else:
            rule_index = len(rule_set)
            rule_set.append(self.rule)
        output_array.append("%d " % rule_index)
        return line_length + len("%d " % rule_index)

    def get_rule(self, rule_set):
        """docstring for get_rule"""
        if self.rule in rule_set:
            rule_index = rule_set.index(self.rule)
        else:
            rule_index = len(rule_set)
            rule_set.append(self.rule)
        return RuleIndex(rule_index)

    def print_rule_expansion(self, rule_set, output_array, line_length):
        """docstring for print_rule_expansion"""
        return self.rule.print_rule_expansion(rule_set, output_array, line_length)

    cpdef delete(self): # Changed to cpdef
        """
        Cleans up for symbol deletion: removes hash table entry and decrements
        rule reference count.
        """
        (<Symbol>self.prev).join(self.next) # Cast
        self.delete_digram()
        self.rule.decrement_reference_count()

cdef class Guard(Symbol):
    """
    The guard symbol in the linked list of symbols that make up the rule.
    It points forward to the first symbol in the rule, and backwards to the last
    symbol in the rule. Its own value points to the rule data structure, so that
    symbols can find out which rule they're in.
    """
    # Attribute rule is defined in symbol.pxd
    # cdef public object rule

    def __init__(self, grammar, rule_obj): # rule_obj should be Rule type
        super(Guard, self).__init__(grammar)
        self.rule = rule_obj

    cpdef bint is_guard(self): return True # Changed to cpdef

    cpdef object value(self): # Added object return type, changed to cpdef
        """docstring for value"""
        return RuleIndex(self.rule.unique_number)

    cpdef object string_value(self): # Added object return type, changed to cpdef
        """docstring for string_value"""
        return "rule(%d)" % self.rule.unique_number

    cpdef delete(self): # Changed to cpdef
        """
        Cleans up for symbol deletion: removes hash table entry and decrements
        rule reference count.
        """
        (<Symbol>self.prev).join(self.next) # Cast
