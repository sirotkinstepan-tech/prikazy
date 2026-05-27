from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.tenant import Tenant
from app.models.user import User


class TenantRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, tenant_id: UUID) -> Tenant | None:
        return self.session.get(Tenant, tenant_id)

    def add(self, tenant: Tenant) -> Tenant:
        self.session.add(tenant)
        return tenant

    def get_by_name(self, name: str) -> Tenant | None:
        return self.session.scalars(select(Tenant).where(Tenant.name == name).limit(1)).first()


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, user_id: UUID) -> User | None:
        return self.session.get(User, user_id)

    def get_for_tenant(self, user_id: UUID, tenant_id: UUID) -> User | None:
        return self.session.scalars(
            select(User)
            .where(User.id == user_id, User.tenant_id == tenant_id)
            .limit(1)
        ).first()

    def get_by_email(self, email: str) -> User | None:
        return self.session.scalars(
            select(User).where(User.email == email.lower().strip()).limit(1)
        ).first()

    def add(self, user: User) -> User:
        self.session.add(user)
        return user

    def list_for_tenant(self, tenant_id: UUID) -> list[User]:
        return list(
            self.session.scalars(
                select(User)
                .where(User.tenant_id == tenant_id)
                .order_by(User.full_name.asc())
            )
        )

    def list_all(self) -> list[User]:
        return list(self.session.scalars(select(User).order_by(User.full_name.asc())))
