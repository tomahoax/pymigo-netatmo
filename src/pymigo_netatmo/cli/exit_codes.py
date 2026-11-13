"""Process exit codes. They are part of the command line contract."""

from typing import Final

EXIT_OK: Final = 0
EXIT_ERROR: Final = 1
EXIT_USAGE: Final = 2
EXIT_RETRY: Final = 3
EXIT_AUTH: Final = 4
EXIT_INTERRUPTED: Final = 130
