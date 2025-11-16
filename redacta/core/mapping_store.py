from typing import Optional


class MappingStore:
    """Simple in-memory store for placeholder mappings.
    
    This class stores the mapping between placeholders and their
    encrypted original values. Future versions could extend this
    to use Redis or other persistent stores.
    """
    
    def __init__(self):
        """Initialize an empty mapping store."""
        self._store: dict[str, bytes] = {}
    
    def set(self, placeholder: str, value: bytes) -> None:
        """Store a placeholder-to-value mapping.
        
        Args:
            placeholder: The placeholder key (e.g., '@@PERSON_1@@')
            value: The encrypted original value
        """
        self._store[placeholder] = value
    
    def get(self, placeholder: str) -> Optional[bytes]:
        """Retrieve the value for a placeholder.
        
        Args:
            placeholder: The placeholder key
            
        Returns:
            The encrypted value, or None if not found
        """
        return self._store.get(placeholder)
    
    def remove(self, placeholder: str) -> bool:
        """Remove a placeholder from the store.
        
        Args:
            placeholder: The placeholder key to remove
            
        Returns:
            True if the placeholder was found and removed, False otherwise
        """
        if placeholder in self._store:
            del self._store[placeholder]
            return True
        return False
    
    def get_all(self) -> dict[str, bytes]:
        """Get all mappings.
        
        Returns:
            Dictionary of all placeholder-to-value mappings
        """
        return self._store.copy()
    
    def clear(self) -> None:
        """Clear all mappings."""
        self._store.clear()
    
    def __len__(self) -> int:
        """Return the number of stored mappings."""
        return len(self._store)
