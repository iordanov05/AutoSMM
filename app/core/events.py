from sqlalchemy import event
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.models.user_group_association import UserGroupAssociation
from app.models.group import Group
import logging

logger = logging.getLogger(__name__)

# 1️⃣ Перед удалением связи запоминаем ID группы
@event.listens_for(UserGroupAssociation, "before_delete")
def track_deleted_group_ids(mapper, connection, target):
    session = Session.object_session(target)
    if session:
        if not hasattr(session, "_deleted_group_ids"):
            session._deleted_group_ids = set()
        session._deleted_group_ids.add(target.vk_group_id)

# 2️⃣ После коммита удаляем группы, если у них больше нет связей
@event.listens_for(Session, "after_commit")
def after_commit_user_group_association(session):
    if not hasattr(session, "_deleted_group_ids"):
        return

    group_ids_to_check = session._deleted_group_ids

    with SessionLocal() as new_session:
        for vk_group_id in group_ids_to_check:
            remaining_associations = new_session.query(UserGroupAssociation).filter_by(vk_group_id=vk_group_id).count()

            logger.info(f"🔍 Осталось связей с группой {vk_group_id}: {remaining_associations}")

            if remaining_associations == 0:
                logger.info(f"❌ Группа {vk_group_id} больше не связана ни с одним пользователем. Удаляем...")
                new_session.query(Group).filter_by(vk_group_id=vk_group_id).delete()
                new_session.commit()
                logger.info(f"✅ Группа {vk_group_id} удалена из базы данных.")

    # Очищаем сохраненные ID
    session._deleted_group_ids.clear()
