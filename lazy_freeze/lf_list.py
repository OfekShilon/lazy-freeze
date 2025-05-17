from collections import UserList
import traceback


class lf_list(UserList):
    """
    Lazy-freeze list class
    ======================
    A *hashable* list-like container that raises an error if modification is attempted after its hash has been taken
    (like being put into a set or used as a dictionary key).
    
    When initialized with debug=True:
    (1) The stack trace at the time of hash calculation is captured and reported in error messages.
    (2) An error is emitted if an un-hashable object is added to the list.

    The choice was made not to inherit the built-in list class, as that would imply lf_list is usable everywhere a
    list is expected - which isn't the case.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.hash_taken = False
        self._debug = kwargs.get('debug', False)
        self._hash_stack = None
        
    def __hash__(self):
        self.hash_taken = True
        if self._debug:
            self._hash_stack = traceback.extract_stack()
        return hash(tuple(self.data))
    
    def validate(self, value=None):
        if self._debug:
            if value is not None and not hasattr(value, '__hash__'):
                raise TypeError(f"Attempted adding an unhashable object {value} to lf_list")
            
        if self.hash_taken:
            if self._debug:
                raise TypeError(f"Cannot modify lf_list, hash was taken at {self._hash_stack}")
            else:
                raise TypeError(f"Cannot modify lf_list after hash is taken")
        
    def validate_sequence(self, sequence):
        if self._debug:
            for item in sequence:
                if not hasattr(item, '__hash__'):
                    raise TypeError(f"Attempted adding an unhashable object {item} to lf_list")
        if self.hash_taken:
            if self._debug:
                raise TypeError(f"Cannot modify lf_list, hash was taken at {self._hash_stack}")
            else:
                raise TypeError(f"Cannot modify lf_list after hash is taken")
        
    def __setitem__(self, index, value):
        self.validate(value)
        self.data[index] = value
        
    def __delitem__(self, index):
        self.validate()
        del self.data[index]

    def append(self, value):
        self.validate(value)
        self.data.append(value)
        return self
    
    def extend(self, iterable):
        self.validate_sequence()
        self.data.extend(iterable)
        return self
    
    def insert(self, index, value):
        self.validate(value)
        self.data.insert(index, value)
        return self
    
    def pop(self, index=-1):
        self.validate()
        return self.data.pop(index)
    
    def remove(self, value):
        self.validate()
        self.data.remove(value)
        return self
    
    def clear(self):
        self.validate()
        self.data.clear()
        return self
    
    def reverse(self):
        self.validate()
        self.data.reverse()
        return self
    
    def sort(self, *args, **kwargs):
        self.validate()
        self.data.sort(*args, **kwargs)
        return self

    def __add__(self, other):
        self.validate_sequence(other)
        self.data += other
        return self
    
    def __iadd__(self, other):
        self.validate_sequence(other)
        self.data += other
        return self
