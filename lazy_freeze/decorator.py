import functools
import traceback
from typing import Any, Callable, Dict, Type, TypeVar, cast

# Type variable for the class being decorated
T = TypeVar('T', bound=Type[object])


def lazy_freeze(cls=None, *, debug: bool = False, protected_attrs: list = None):
    """
    Class decorator that makes an object immutable after its hash is taken.
    Supports both @lazy_freeze and @lazy_freeze(debug=True, ...).

    The decorator adds or overrides:
    - __hash__: to set hash_taken=True when called
    - __setattr__, __delattr__: to prevent attribute modification if hash_taken is True
    - __setitem__, __delitem__: to prevent item modification if hash_taken is True
    - In-place operations (__iadd__, __isub__, etc.): to prevent in-place modifications

    Args:
        cls: The class to be decorated
        debug: If True, captures stack trace at hash time and includes it in error messages
        protected_attrs: List of attribute names to protect after hash is taken.
                         If None or empty, all attributes will be protected.

    Returns:
        The decorated class

    Raises:
        AssertionError: If the class does not have a custom __hash__ method
        TypeError: If applied to a non-class entity

    Example:
        @lazy_freeze
        class Person:
            def __init__(self, name, age):
                self.name = name
                self.age = age

            def __hash__(self):
                return hash((self.name, self.age))

        # With debug enabled
        @lazy_freeze(debug=True)
        class DebugPerson:
            def __init__(self, name, age):
                self.name = name
                self.age = age

            def __hash__(self):
                return hash((self.name, self.age))
                
        # With specific attributes protected
        @lazy_freeze(protected_attrs=["name", "age"])
        class PartiallyProtectedPerson:
            def __init__(self, name, age, description):
                self.name = name
                self.age = age
                self.description = description  # Not used in hash, can be modified
                
            def __hash__(self):
                return hash((self.name, self.age))  # Only uses name and age
    """
    def wrap(actual_cls):
        # Check that the decorated object is a class and not a function or other entity
        if not isinstance(actual_cls, type):
            raise TypeError(
                f"@lazy_freeze can only be applied to classes, not {type(actual_cls).__name__}. "
                f"Got {actual_cls} which is a {type(actual_cls).__name__}, not a class."
            )

        # Check if class has a custom __hash__ method (not the one from object)
        has_custom_hash = hasattr(
            actual_cls, '__hash__') and actual_cls.__hash__ is not object.__hash__

        # Assert that the class has a custom hash implementation
        assert has_custom_hash, (
            f"Class '{actual_cls.__name__}' must implement a custom __hash__ method to use the @lazy_freeze decorator. "
            f"Implement __hash__ to define the object's hash value, which should be consistent with equality (__eq__)."
        )

        # Store the original hash method
        original_hash = actual_cls.__hash__

        # Define core attribute mutation methods (always present via object)
        mutating_methods = {
            '__setattr__': (object.__setattr__, 
                            lambda name, value: f"modify attribute '{name}' of"),
            '__delattr__': (object.__delattr__, 
                            lambda name: f"delete attribute '{name}' from"),
        }
        
        # Define all optional mutating operations
        optional_operations = {
            # Item mutation operations
            '__setitem__': lambda key, value: f"modify item '{key}' of",
            '__delitem__': lambda key: f"delete item '{key}' from",
            
            # In-place operations
            '__iadd__': lambda other: f"modify with in-place addition",
            '__isub__': lambda other: f"modify with in-place subtraction",
            '__imul__': lambda other: f"modify with in-place multiplication",
            '__itruediv__': lambda other: f"modify with in-place division",
            '__ifloordiv__': lambda other: f"modify with in-place floor division",
            '__imod__': lambda other: f"modify with in-place modulo",
            '__ipow__': lambda other: f"modify with in-place power",
            '__ilshift__': lambda other: f"modify with in-place left shift",
            '__irshift__': lambda other: f"modify with in-place right shift",
            '__iand__': lambda other: f"modify with in-place bitwise AND",
            '__ixor__': lambda other: f"modify with in-place bitwise XOR",
            '__ior__': lambda other: f"modify with in-place bitwise OR",
            '__imatmul__': lambda other: f"modify with in-place matrix multiplication",
        }
        
        # Only add optional operations that exist in the class
        for op_name, error_formatter in optional_operations.items():
            if hasattr(actual_cls, op_name):
                original_method = getattr(actual_cls, op_name)
                mutating_methods[op_name] = (original_method, error_formatter)

        # Update core methods if the class has its own implementations
        for method_name in list(mutating_methods.keys()):
            if method_name in ('__setattr__', '__delattr__') and hasattr(actual_cls, method_name):
                mutating_methods[method_name] = (getattr(actual_cls, method_name), 
                                                mutating_methods[method_name][1])

        def __hash__(self: Any) -> int:
            """Calculate hash and mark the object as hash-taken. In debug mode, capture stack trace."""
            hash_value = original_hash(self)

            # Use direct attribute setting to avoid recursion with __setattr__
            object.__setattr__(self, 'hash_taken', True)
            
            # In debug mode, capture stack trace
            if debug:
                stack_trace = ''.join(traceback.format_stack()[
                                      :-1])  # Exclude current frame
                object.__setattr__(self, '_hash_stack_trace', stack_trace)

            return hash_value

        def get_error_message(self: Any, operation: str) -> str:
            """Generate an appropriate error message based on debug mode."""
            if debug and hasattr(self, '_hash_stack_trace'):
                return (
                    f"Cannot {operation} {actual_cls.__name__} after its hash has been taken.\n"
                    f"Hash was calculated at:\n{self._hash_stack_trace}"
                )
            else:
                return f"Cannot {operation} {actual_cls.__name__} after its hash has been taken"

        # Set the hash method
        setattr(actual_cls, '__hash__', __hash__)

        # Create new methods for each mutating operation
        for method_name, (original_method, error_formatter) in mutating_methods.items():
            # Skip if the original method doesn't exist and it's not a core attribute method
            if original_method is None and method_name not in ('__setattr__', '__delattr__'):
                continue
                
            # Create a wrapped method that checks hash_taken
            def make_protected_method(method_name=method_name, 
                                      original=original_method,
                                      format_error=error_formatter):
                def protected_method(self: Any, *args: Any, **kwargs: Any) -> Any:
                    if hasattr(self, 'hash_taken') and self.hash_taken:
                        # Check if we're only protecting specific attributes
                        if protected_attrs:
                            # For __setattr__ and __delattr__, check if the attribute is protected
                            if method_name == '__setattr__' or method_name == '__delattr__':
                                attr_name = args[0] if args else None
                                if attr_name not in protected_attrs:
                                    return original(self, *args, **kwargs)

                        # Generate the appropriate error message
                        operation = format_error(*args)
                        raise TypeError(get_error_message(self, operation))
                    
                    # Call the original method if it exists
                    if original is not None:
                        return original(self, *args, **kwargs)
                    
                    # For optional methods like __setitem__, raise a TypeError if not supported
                    if method_name in ('__setitem__', '__delitem__'):
                        raise TypeError(f"{actual_cls.__name__} does not support {method_name[2:-2]} operations")
                    
                    # Default fallback for other methods (should not be reached in practice)
                    return None
                
                return protected_method
            
            # Set the method on the class
            setattr(actual_cls, method_name, make_protected_method())

        return actual_cls

    if cls is None:
        return wrap
    else:
        return wrap(cls)
