from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.orm import Session

from app.auth.password import hash_password
from app.core.errors import ApplicationError
from app.core.document_sections import all_document_types
from app.core.section_permissions import parse_section_access_level
from app.models.enums import SectionAccessLevel, UserRole
from app.models.user import User
from app.repositories.user_section_access import UserSectionAccessRepository
from app.repositories.users import UserRepository


@dataclass(frozen=True)
class CreateUserCommand:
    tenant_id: UUID
    email: str
    password: str
    full_name: str
    role: UserRole
    section_access: dict[str, SectionAccessLevel] | None = None


@dataclass(frozen=True)
class UpdateUserCommand:
    user_id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    password: str | None = None
    section_access: dict[str, SectionAccessLevel] | None = None


class UserService:
    MIN_PASSWORD_LENGTH = 6

    def __init__(self, session: Session):
        self.session = session
        self.users = UserRepository(session)
        self.section_access = UserSectionAccessRepository(session)

    def create_user(self, command: CreateUserCommand) -> User:
        email = command.email.lower().strip()
        full_name = command.full_name.strip()
        self._validate_email(email)
        self._validate_full_name(full_name)
        self._validate_password(command.password)
        self._validate_role(command.role)

        if self.users.get_by_email(email) is not None:
            raise ApplicationError(
                "Пользователь с таким email уже существует",
                status_code=409,
                code="email_taken",
            )

        user = User(
            tenant_id=command.tenant_id,
            email=email,
            password_hash=hash_password(command.password),
            full_name=full_name,
            role=command.role.value,
        )
        self.users.add(user)
        self.session.flush()
        if command.role == UserRole.EMPLOYEE and command.section_access is not None:
            self._save_section_access(user.id, command.section_access)
        self.session.commit()
        return user

    def update_user(
        self,
        command: UpdateUserCommand,
        *,
        acting_user_id: UUID,
    ) -> User:
        user = self._get_for_tenant(command.user_id, command.tenant_id)
        email = command.email.lower().strip()
        full_name = command.full_name.strip()
        self._validate_email(email)
        self._validate_full_name(full_name)
        self._validate_role(command.role)

        existing = self.users.get_by_email(email)
        if existing is not None and existing.id != user.id:
            raise ApplicationError(
                "Пользователь с таким email уже существует",
                status_code=409,
                code="email_taken",
            )

        if user.id == acting_user_id:
            if command.role != UserRole.ADMIN:
                raise ApplicationError(
                    "Нельзя снять с себя роль администратора",
                    status_code=400,
                    code="self_demote_forbidden",
                )
            if not command.is_active:
                raise ApplicationError(
                    "Нельзя деактивировать свой аккаунт",
                    status_code=400,
                    code="self_deactivate_forbidden",
                )

        if command.password:
            self._validate_password(command.password)
            user.password_hash = hash_password(command.password)

        user.email = email
        user.full_name = full_name
        user.role = command.role.value
        user.is_active = command.is_active
        if command.section_access is not None:
            if command.role == UserRole.EMPLOYEE:
                self._save_section_access(user.id, command.section_access)
            else:
                self.section_access.replace_for_user(user.id, {})
        self.session.commit()
        return user

    def get_section_access_for_user(self, user_id: UUID) -> dict[str, SectionAccessLevel]:
        return self.section_access.list_for_user(user_id)

    @staticmethod
    def parse_section_access_from_form(form_levels: dict[str, str]) -> dict[str, SectionAccessLevel]:
        access: dict[str, SectionAccessLevel] = {}
        for doc_type in (item.value for item in all_document_types()):
            raw = form_levels.get(doc_type, SectionAccessLevel.NONE.value)
            access[doc_type] = parse_section_access_level(raw)
        return access

    def _save_section_access(
        self,
        user_id: UUID,
        access: dict[str, SectionAccessLevel],
    ) -> None:
        self.section_access.replace_for_user(user_id, access)

    def toggle_active(
        self,
        *,
        user_id: UUID,
        tenant_id: UUID,
        acting_user_id: UUID,
    ) -> User:
        user = self._get_for_tenant(user_id, tenant_id)
        if user.id == acting_user_id:
            raise ApplicationError(
                "Нельзя деактивировать свой аккаунт",
                status_code=400,
                code="self_deactivate_forbidden",
            )
        user.is_active = not user.is_active
        self.session.commit()
        return user

    def _get_for_tenant(self, user_id: UUID, tenant_id: UUID) -> User:
        user = self.users.get_for_tenant(user_id, tenant_id)
        if user is None:
            raise ApplicationError(
                "Пользователь не найден",
                status_code=404,
                code="user_not_found",
            )
        return user

    @staticmethod
    def _validate_email(email: str) -> None:
        if not email or "@" not in email:
            raise ApplicationError(
                "Укажите корректный email",
                status_code=400,
                code="invalid_email",
            )

    @staticmethod
    def _validate_full_name(full_name: str) -> None:
        if not full_name:
            raise ApplicationError(
                "Укажите имя пользователя",
                status_code=400,
                code="invalid_full_name",
            )

    def _validate_password(self, password: str) -> None:
        if len(password) < self.MIN_PASSWORD_LENGTH:
            raise ApplicationError(
                f"Пароль должен быть не короче {self.MIN_PASSWORD_LENGTH} символов",
                status_code=400,
                code="invalid_password",
            )

    @staticmethod
    def _validate_role(role: UserRole) -> None:
        if role not in (UserRole.ADMIN, UserRole.EMPLOYEE):
            raise ApplicationError(
                "Недопустимая роль",
                status_code=400,
                code="invalid_role",
            )
