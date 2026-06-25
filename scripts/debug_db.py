import asyncio
import os
import pprint

os.environ['DATABASE_URL'] = 'postgresql+asyncpg://neondb_owner:npg_kS7IVmZ2ptds@ep-falling-violet-ao7vgczb-pooler.c-2.ap-southeast-1.aws.neon.tech/neondb?ssl=require'

import backend.app.db.session as db_session
from backend.app.db.models import IngestionJob
from sqlalchemy import select

async def run():
    db_session.init_db(os.environ['DATABASE_URL'])
    async with db_session._engine.connect() as conn:
        result = await conn.execute(
            select(IngestionJob.id, IngestionJob.doc_id, IngestionJob.current_task, IngestionJob.status, IngestionJob.started_at)
            .order_by(IngestionJob.started_at.desc())
            .limit(5)
        )
        pprint.pprint(result.all())
    await db_session._engine.dispose()

asyncio.run(run())
