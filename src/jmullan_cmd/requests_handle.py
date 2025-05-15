import logging

import requests

from jmullan_logging.helpers import logging_context  # type: ignore[import-not-found]

logger = logging.getLogger(__name__)


class RequestsHandle:
    def __init__(self, url: str):
        logger.debug("Opening url")
        self.url = url
        self.response = requests.get(url, stream=True)
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def close(self, *args, **kwargs):  # real signature unknown
        """
        Close the IO object.

        Attempting any further operation after the object is closed
        will raise a ValueError.

        This method has no effect if the file is already closed.
        """
        self._closed = True
        try:
            if self.response is not None:
                self.response.close()
                self.response = None
        except Exception:
            with logging_context(external_http_url=self.url):
                logger.exception("Error closing request")

    def getvalue(self, *args, **kwargs) -> str:  # real signature unknown
        """Retrieve the entire contents of the object."""
        return self.response.text

    def read(self, size: int | None = None) -> str | None:  # real signature unknown
        """
        Read at most size characters, returned as a string.

        If the argument is negative or omitted, read until EOF
        is reached. Return an empty string at EOF.
        """
        try:
            if size is None:
                return self.response.text
            else:
                # yield from self.response.iter_content(chunk_size=size, decode_unicode=True)
                return "".join(self.response.iter_content(chunk_size=size, decode_unicode=True))
        finally:
            self.close()

    def readable(self, *args, **kwargs):  # real signature unknown
        """Returns True if the IO object can be read."""
        return not self._closed

    def readline(self, size=-1, /):  # real signature unknown
        """
        Read until newline or EOF.

        Returns an empty string if EOF is hit immediately.
        """
        yield from self.response.iter_lines(chunk_size=size, decode_unicode=True)
        self.close()

    def seek(self, *args, **kwargs):  # real signature unknown
        """
        Change stream position.

        Seek to character offset pos relative to position indicated by whence:
            0  Start of stream (the default).  pos should be >= 0;
            1  Current position - pos must be 0;
            2  End of stream - pos must be 0.
        Returns the new absolute position.
        """
        raise NotImplementedError("Cannot seek from requests")

    @staticmethod
    def seekable(*args, **kwargs):  # real signature unknown
        """Returns True if the IO object can be seeked."""
        return False

    def tell(self, *args, **kwargs):  # real signature unknown
        """Tell the current file position."""
        if self.readable():
            return self.response.raw.tell()

    def truncate(self, *args, **kwargs):  # real signature unknown
        """
        Truncate size to pos.

        The pos argument defaults to the current file position, as
        returned by tell().  The current file position is unchanged.
        Returns the new absolute position.
        """
        raise NotImplementedError("Cannot seek from requests")

    def writable(self, *args, **kwargs):  # real signature unknown
        """Returns True if the IO object can be written."""
        return False

    def write(self, *args, **kwargs):  # real signature unknown
        """
        Write string to file.

        Returns the number of characters written, which is always equal to
        the length of the string.
        """
        raise NotImplementedError("Cannot seek from requests")
