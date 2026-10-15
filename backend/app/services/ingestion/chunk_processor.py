from sqlalchemy.ext.asyncio import (
    AsyncSession,
)

import json

from app.services.ingestion.sensitivity_classifier import (
    SensitivityClassifier,
)


class ChunkProcessor:

    @staticmethod
    async def process_chunk(

        db: AsyncSession,

        chunk: dict,

        write_review_file: bool = True,

    ):
        
        
        print("in ra chunk", chunk)

        security_level = (
            chunk
            .get("metadata", {})
            .get("security_level")
        )

        #
        # Không cần AI
        #

        if security_level == "PUBLIC":

            sensitivity = 1

        elif security_level == "INTERNAL":

            sensitivity = 2

        #
        # COMBINE -> AI Detect
        #

        else:

            sensitivity = await (

                SensitivityClassifier
                .detect(

                    db=db,

                    content=chunk["content"],

                    security_level=security_level,

                    department=
                    chunk["metadata"].get(
                        "department"
                    ),

                )

            )

        # --------------------------
        # Metadata Enrichment
        # --------------------------

        result = {

            "id":
            chunk.get("id"),

            "department":
            chunk.get(
                "metadata",
                {},
            ).get(
                "department",
            ),

            "security_level":
            security_level,

            "sensitivity":
            sensitivity,

            "processed":
            True,

            "content_preview":
            chunk.get(
                "content",
                "",
            )[:300],

        }

        # --------------------------
        # Review File
        # --------------------------

        if not write_review_file:

            return result

        with open(

            "review_chunks.json",

            "a",

            encoding="utf-8",

        ) as f:

            json.dump(

                result,

                f,

                ensure_ascii=False,

            )

            f.write("\n")

        return result