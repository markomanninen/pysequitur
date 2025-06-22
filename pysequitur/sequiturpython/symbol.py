# Original Cython imports removed:
# import cython
# from .symbol import Symbol as PySymbol # Not needed for pure Python version
# from .rule cimport Rule # Will be a Python import if needed

# Standard Python import for Rule, assuming it will also be de-Cythonized
# or was originally a Python class.
# from .rule import Rule # Moved into methods to break circular import

# Few constants for presentation logics
RULE_INDEX_STR = "^%s"

class RuleIndex(int):
    """
    Reason to use separate class for rule index values is that 
    they must be separated from possible numerical sequence values
    """
    def __repr__(self):
        return RULE_INDEX_STR % int(self) # Use int(self) to avoid recursion

class Symbol(object):
    """docstring for Symbol"""
    # Cython 'cdef public' attributes (grammar, next, prev) become
    # regular instance attributes, typically initialized in __init__.

    def __init__(self, grammar):
        """docstring for __init__"""
        self.grammar = grammar # grammar will be an instance of the Grammar class
        self.next = None
        self.prev = None
        # Subclass-specific attributes like 'rule' or 'terminal'
        # will be initialized in their respective __init__ methods.

    def value(self):
        # Base implementation, should be overridden by subclasses.
        raise NotImplementedError("This method should be overridden in subclasses")

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
    def factory(grammar, value):
        """docstring for factory"""
        from .rule import Rule # Moved here
        # Removed Cython specific <Terminal>value, etc. Python handles types dynamically.
        if isinstance(value, str):
            return Terminal(grammar, value)
        elif isinstance(value, Terminal): # value is already a Terminal instance
            return Terminal(grammar, value.terminal)
        elif isinstance(value, NonTerminal): # value is already a NonTerminal instance
            return NonTerminal(grammar, value.rule)
        elif isinstance(value, Rule): # value is a Rule instance
            return NonTerminal(grammar, value)
        else:
            raise TypeError("type(value) == %s" % type(value))

    @staticmethod
    def guard(grammar, rule_instance): # 'value' renamed to 'rule_instance' for clarity
        """docstring for guard"""
        return Guard(grammar, rule_instance)

    def join(self, right): # Removed 'Symbol' type hint from 'right'
        """
        Links two symbols together, removing any old digram from the hash table.
        """
        if self.next:
            self.delete_digram()
            
            if ((right.prev is not None) and (right.next is not None) and
                right.value() == right.prev.value() and
                right.value() == right.next.value()):
                self.grammar.add_index(right)
            if ((self.prev is not None) and (self.next is not None) and
                self.value() == self.next.value() and
                self.value() == self.prev.value()):
                self.grammar.add_index(self)
        self.next = right
        right.prev = self

    def delete_digram(self):
        """Removes the digram from the hash table"""
        # Removed Cython casts like (<Symbol>self.next)
        if self.is_guard() or self.next.is_guard():
            pass
        else:
            self.grammar.clear_index(self)

    def insert_after(self, symbol): # Removed 'Symbol' type hint
        """Inserts a symbol after this one"""
        symbol.join(self.next)
        self.join(symbol)

    def is_guard(self): return False # Removed 'bint' return type

    def expand(self):
        """
        This symbol is the last reference to its rule. It is deleted, and the
        contents of the rule substituted in its place.
        """
        # Removed cdef declarations for left, right, first, last
        left = self.prev
        right = self.next
        # Assuming self is NonTerminal, so self.rule exists.
        # No cast needed for self.rule in Python.
        first = self.rule.first()
        last = self.rule.last()
        
        self.grammar.clear_index(self)
        left.join(first)
        last.join(right)
        self.grammar.add_index(last)

    def propagate_change(self):
        """docstring for propagate_change"""
        # Removed cdef declaration for match
        # Removed Cython casts
        if self.is_guard() or self.next.is_guard():
            if (self.next.is_guard() or self.next.next.is_guard()):
                return
            match = self.grammar.get_index(self.next)
            if not match:
                self.grammar.add_index(self.next)
            elif match.next != self.next:
                self.next.process_match(match)
        else:
            match = self.grammar.get_index(self)
            if not match:
                self.grammar.add_index(self)
                if (self.next.is_guard() or self.next.next.is_guard()):
                    return
                match = self.grammar.get_index(self.next)
                if not match:
                    self.grammar.add_index(self.next)
                elif match.next != self.next:
                    self.next.process_match(match)
            elif match.next != self:
                self.process_match(match)

    def substitute(self, rule_obj):
        """Replace a digram with a non-terminal"""
        # Removed cdef declaration for prev_sym
        prev_sym = self.prev
        prev_sym.next.delete()
        prev_sym.next.delete() # This was effectively prev_sym.next.next in the original list
        prev_sym.insert_after(Symbol.factory(self.grammar, rule_obj)) # Symbol.factory, not PySymbol

    def process_match(self, match): # Removed 'Symbol' type hint
        """Deal with a matching digram"""
        from .rule import Rule # Moved here
        # Removed cdef declaration for rule_obj
        rule_obj = None

        if match.prev.is_guard() and match.next.next.is_guard():
            rule_obj = match.prev.rule
            self.substitute(rule_obj)
            self.prev.propagate_change()
        else:
            rule_obj = Rule(self.grammar) # Assumes Rule is importable
            rule_obj.last().insert_after(Symbol.factory(self.grammar, self)) # Symbol.factory
            rule_obj.last().insert_after(Symbol.factory(self.grammar, self.next)) # Symbol.factory
            self.grammar.add_index(rule_obj.first())
            
            match.substitute(rule_obj)
            match.prev.propagate_change()
            self.substitute(rule_obj)
            self.prev.propagate_change()

        if isinstance(rule_obj.first(), NonTerminal) and rule_obj.first().rule.reference_count == 1:
            rule_obj.first().expand()

    def string_value(self): # Changed from cpdef object to def
        """docstring for string_value"""
        raise NotImplementedError("This method should be overridden in subclasses")

    def hash_value(self): # Changed from cpdef to def
        """docstring for hash_value"""
        # Removed (<Symbol>self.next) cast
        return (self.string_value(), self.next.string_value())

class Terminal(Symbol):
    """docstring for Terminal"""
    # self.terminal is initialized in __init__

    def __init__(self, grammar, terminal_value):
        super(Terminal, self).__init__(grammar)
        self.terminal = terminal_value # Standard Python attribute
        
    def value(self): # Changed from cpdef object to def
        """docstring for value"""
        return self.terminal

    def string_value(self): # Changed from cpdef object to def
        return self.terminal

    def delete(self): # Changed from cpdef to def
        """
        Cleans up for symbol deletion: removes hash table entry and decrements
        rule reference count.
        """
        self.prev.join(self.next) # Removed cast
        self.delete_digram()

class NonTerminal(Symbol):
    """docstring for NonTerminal"""
    # self.rule is initialized in __init__

    def __init__(self, grammar, rule_obj):
        super(NonTerminal, self).__init__(grammar)
        self.rule = rule_obj # Standard Python attribute
        self.rule.increment_reference_count()

    def value(self): # Changed from cpdef object to def
        """docstring for value"""
        return RuleIndex(self.rule.unique_number)

    def string_value(self): # Changed from cpdef object to def
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

    def delete(self): # Changed from cpdef to def
        """
        Cleans up for symbol deletion: removes hash table entry and decrements
        rule reference count.
        """
        self.prev.join(self.next) # Removed cast
        self.delete_digram()
        self.rule.decrement_reference_count()

class Guard(Symbol):
    """
    The guard symbol in the linked list of symbols that make up the rule.
    It points forward to the first symbol in the rule, and backwards to the last
    symbol in the rule. Its own value points to the rule data structure, so that
    symbols can find out which rule they're in.
    """
    # self.rule is initialized in __init__

    def __init__(self, grammar, rule_obj):
        super(Guard, self).__init__(grammar)
        self.rule = rule_obj # Standard Python attribute

    def is_guard(self): return True # Removed 'bint' return type, was cpdef

    def value(self): # Changed from cpdef object to def
        """docstring for value"""
        return RuleIndex(self.rule.unique_number)

    def string_value(self): # Changed from cpdef object to def
        """docstring for string_value"""
        return "rule(%d)" % self.rule.unique_number

    def delete(self): # Changed from cpdef to def
        """
        Cleans up for symbol deletion: removes hash table entry and decrements
        rule reference count. (Note: Guard's original delete didn't call delete_digram)
        """
        self.prev.join(self.next) # Removed cast
