import dolphin_memory_engine

### Read
def read_byte(console_address: int) -> int:
    """
    Read a 1-byte short from Dolphin memory.

    :param console_address: Address to read from.
    :return: The value read from memory.
    """
    return int.from_bytes(dolphin_memory_engine.read_bytes(console_address, 1), byteorder="big")

def read_2byte(console_address: int) -> int:
    """
    Read a 2-byte short from Dolphin memory.

    :param console_address: Address to read from.
    :return: The value read from memory.
    """
    return int.from_bytes(dolphin_memory_engine.read_bytes(console_address, 2), byteorder="big")

def read_4byte(console_address: int) -> int:
    """
    Read a 4-byte short from Dolphin memory.

    :param console_address: Address to read from.
    :return: The value read from memory.
    """
    return int.from_bytes(dolphin_memory_engine.read_bytes(console_address, 4), byteorder="big")

def read_string(console_address: int, strlen: int) -> str:
    """
    Read a string from Dolphin memory.

    :param console_address: Address to start reading from.
    :param strlen: Length of the string to read.
    :return: The string.
    """
    return dolphin_memory_engine.read_bytes(console_address, strlen).split(b"\0", 1)[0].decode()

### Write
def write_byte(console_address: int, value: int) -> None:
    """
    Write a 1-byte short to Dolphin memory.

    :param console_address: Address to write to.
    :param value: Value to write.
    """
    dolphin_memory_engine.write_bytes(console_address, value.to_bytes(1, byteorder="big"))

def write_2byte(console_address: int, value: int) -> None:
    """
    Write a 2-byte short to Dolphin memory.

    :param console_address: Address to write to.
    :param value: Value to write.
    """
    dolphin_memory_engine.write_bytes(console_address, value.to_bytes(2, byteorder="big"))

def write_4byte(console_address: int, value: int) -> None:
    """
    Write a 4-byte short to Dolphin memory.

    :param console_address: Address to write to.
    :param value: Value to write.
    """
    dolphin_memory_engine.write_bytes(console_address, value.to_bytes(4, byteorder="big"))

def write_string(console_address: int, value: str, null_terminate: bool = True) -> None:
        """
        Write a string to Dolphin memory.

        :param console_address: Address to write to.
        :param value: String to write.
        :param null_terminate: Whether to add a null terminator at the end (default: True).
        """
        # Encode the string to bytes
        string_bytes = value.encode('utf-8')
        
        # Add null terminator if requested
        if null_terminate:
            string_bytes += b'\0'
        
        # Write the bytes to memory
        dolphin_memory_engine.write_bytes(console_address, string_bytes)

"""
def write_string_fixed_length(console_address: int, value: str, max_length: int, 
                                 pad_with_null: bool = True) -> None:
        "" "
        Write a string to Dolphin memory with a fixed length.
        
        :param console_address: Address to write to.
        :param value: String to write.
        :param max_length: Maximum length of the string buffer in memory.
        :param pad_with_null: Whether to pad remaining space with null bytes (default: True).
        "" "
        # Encode the string to bytes
        string_bytes = value.encode('utf-8')
        
        # Truncate if too long
        if len(string_bytes) >= max_length:
            string_bytes = string_bytes[:max_length-1] + b'\0'
        else:
            # Add null terminator and pad if necessary
            string_bytes += b'\0'
            if pad_with_null and len(string_bytes) < max_length:
                string_bytes += b'\0' * (max_length - len(string_bytes))
        
        # Write the bytes to memory
        dolphin_memory_engine.write_bytes(console_address, string_bytes)
"""

