class InvalidHash(Exception):
    message = 'Invalid hash!'


class FIleNotFound(Exception):
    message = 'File not found!'
    
    
class UnsupportedMedia(Exception):
    message = 'Document has no content.'