from sqlalchemy.ext.asyncio import (

    create_async_engine,

    async_sessionmaker,

    AsyncSession

)

from sqlalchemy.pool import NullPool

from sqlalchemy.orm import DeclarativeBase

from app.core.settings import settings


DATABASE_URL = settings.DATABASE_URL


engine = create_async_engine(

    DATABASE_URL,

    echo=True,


    connect_args={

        "statement_cache_size":

        0

    },


    poolclass=
    NullPool

)


AsyncSessionLocal = async_sessionmaker(

    bind=
    engine,


    expire_on_commit=
    False,


    class_=
    AsyncSession

)


class Base(
    DeclarativeBase
):
    pass



async def get_db():

    async with (
        AsyncSessionLocal()
    ) as session:

        yield session
