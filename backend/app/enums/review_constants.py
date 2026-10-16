from enum import IntEnum


class ReviewFileLimit(IntEnum):

    MIN = 0
    MAX_FILE_REVIEW = 5


class ReviewConstants:

    MAX_FILE_SIZE = 5 * 1024 * 1024

    MAX_RETRY_COUNT = 3

    ALLOWED_MIME_TYPES = [
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ]

    TEMP_DIRECTORY = "temp/review"
