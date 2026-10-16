from sqlalchemy import (
    
    select
)
from sqlalchemy import func
from sqlalchemy.ext.asyncio import (
    AsyncSession
)

from app.models.ai_model import (
    AIModel
)
from app.schemas.get_ai_model_paged_request import (
    GetAIModelPagedRequest
)
from uuid import UUID


class AIModelRepository:

    @staticmethod
    async def get_all(
        db: AsyncSession
    ):
        query = await db.execute(
            select(
                AIModel
            )
            .where(
                AIModel.is_active == True
            )
            .order_by(
                AIModel.display_name.asc()
            )
        )

        return (
            query
            .scalars()
            .all()
        )

    @staticmethod
    async def get_first_active(
        db: AsyncSession,
    ):
        query = await db.execute(
            select(AIModel)
            .where(AIModel.is_active == True)
            .order_by(AIModel.display_name.asc(), AIModel.id.asc())
            .limit(1)
        )
        return query.scalar_one_or_none()

    @staticmethod
    async def get_default(
        db: AsyncSession
    ):
        query = await db.execute(
            select(
                AIModel
            )
            .where(
                AIModel.is_default == True
            )
        )

        return (
            query
            .scalar_one_or_none()
        )

    @staticmethod
    async def get_by_code(
        db: AsyncSession,
        code: str
    ):
        query = await db.execute(
            select(
                AIModel
            )
            .where(
                AIModel.code == code
            )
        )

        return (
            query
            .scalar_one_or_none()
        )
        
    @staticmethod
    async def get_by_id(
        db: AsyncSession,
        id: UUID,
    ):
        query = await db.execute(
            select(
                AIModel
            )
            .where(
                AIModel.id == id,
                
            )
        )

        return (
            query
            .scalar_one_or_none()
        )
    @staticmethod
    async def create(
        db: AsyncSession,
        model: AIModel,
    ):
        db.add(model)
            
    @staticmethod
    async def update(
        db: AsyncSession,
        model: AIModel,
    ):
        db.add(model)
        
    @staticmethod
    async def get_paged(
        db: AsyncSession,
        request: GetAIModelPagedRequest,
    ) -> tuple[list[AIModel], int]:

        total = await db.scalar(
            select(func.count())
            .select_from(AIModel)
            .where(
                AIModel.is_active == True,
            )
        )

        query = await db.execute(
            select(
                AIModel,
            )
            .where(
                AIModel.is_active == True,
            )
            .order_by(
                AIModel.display_name.asc(),
            )
            .offset(
                (request.page - 1) * request.page_size,
            )
            .limit(
                request.page_size,
            )
        )

        return (
            list(
                query.scalars().all(),
            ),
            total or 0,
        )
        
    @staticmethod
    async def soft_delete(
            db: AsyncSession,
            model: AIModel,
        ) -> None:
    
            model.is_active = False
            db.add(model)
