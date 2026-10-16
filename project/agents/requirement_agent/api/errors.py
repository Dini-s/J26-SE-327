"""One error type for the API; every error response has the shape {"error": {"code": ..., "message": ...}}."""


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message

    def body(self):
        return {"error": {"code": self.code, "message": self.message}}
