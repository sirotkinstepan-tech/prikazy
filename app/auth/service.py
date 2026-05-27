from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.password import hash_password, verify_password
from app.core.section_permissions import resolve_access_for_role
from app.models.enums import SectionAccessLevel, UserRole
from app.models.user import User
from app.repositories.user_section_access import UserSectionAccessRepository
from app.repositories.users import UserRepository


@dataclass(frozen=True)
class AuthenticatedUser:
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: UserRole
    section_access: dict[str, SectionAccessLevel]

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_employee(self) -> bool:
        return self.role == UserRole.EMPLOYEE


class AuthService:
    def __init__(self, session: Session):
        self.session = session
        self.users = UserRepository(session)
        self.section_access = UserSectionAccessRepository(session)

    def authenticate(self, email: str, password: str) -> AuthenticatedUser | None:
        user = self.users.get_by_email(email)
        if user is None or not user.is_active:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return self._to_authenticated(user)

    def get_user(self, user_id: UUID) -> AuthenticatedUser | None:
        user = self.users.get(user_id)
        if user is None or not user.is_active:
            return None
        return self._to_authenticated(user)

    @staticmethod
    def create_password_hash(password: str) -> str:
        return hash_password(password)

    def _to_authenticated(self, user: User) -> AuthenticatedUser:
        role = UserRole(user.role)
        stored = self.section_access.list_for_user(user.id)
        access = resolve_access_for_role(role, stored)
        return AuthenticatedUser(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email,
            full_name=user.full_name,
            role=role,
            section_access=access,
        )
