from pathlib import Path

from shutil import rmtree

from uuid import UUID
from uuid import uuid4

from fastapi import UploadFile

from app.enums.review_constants import (
    ReviewConstants,
)
from app.enums.temp_file_result import (
    TempFileResult,
)


class TempFileService:

    @staticmethod
    async def save(
        job_id: UUID,
        file: UploadFile,
    ) -> TempFileResult:

        root_directory = Path(
            ReviewConstants.TEMP_DIRECTORY,
        )

        job_directory = (
            root_directory / str(job_id)
        )

        job_directory.mkdir(
            parents=True,
            exist_ok=True,
        )

        extension = Path(
            file.filename,
        ).suffix

        file_name = (
            f"{uuid4()}{extension}"
        )

        file_path = (
            job_directory / file_name
        )
        size = 0

        with open(
            file_path,
            "wb",
        ) as output:

            while True:

                chunk = await file.read(
                    1024 * 1024,
                )

                if not chunk:
                    break
                
                size += len(chunk)

                output.write(
                    chunk,
                )

        await file.seek(0)

        return TempFileResult(
            file_path=str(file_path),
            file_size=size,
        )

    @staticmethod
    def exists(
        file_path: str,
    ) -> bool:

        return Path(
            file_path,
        ).exists()

    @staticmethod
    def delete(
        file_path: str,
    ) -> None:

        path = Path(
            file_path,
        )

        if path.exists():

            path.unlink()

    @staticmethod
    def delete_job_directory(
        job_id: UUID,
    ) -> None:

        directory = (
            Path(
                ReviewConstants.TEMP_DIRECTORY,
            )
            / str(job_id)
        )

        if directory.exists():

            rmtree(
                directory,
            )