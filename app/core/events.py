from sqlalchemy import event
from sqlalchemy.orm import Session
from app.core.db import SessionLocal
from app.models.user_group_association import UserGroupAssociation
from app.models.group import Group

@event.listens_for(UserGroupAssociation, "after_delete")
def after_delete_user_group_association(mapper, connection, target):
    with SessionLocal() as session:
        remaining_associations = session.query(UserGroupAssociation).filter_by(vk_group_id=target.vk_group_id).count()
        if remaining_associations == 0:
            session.query(Group).filter_by(vk_group_id=target.vk_group_id).delete()
            session.commit()
