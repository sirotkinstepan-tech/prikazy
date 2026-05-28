from datetime import date, datetime

STATUS_LABELS = {
    "uploaded": "Загружен",
    "queued": "В очереди",
    "processing": "Обрабатывается",
    "processed": "Готов",
    "validated": "Проверен",
    "failed": "Ошибка",
    "archived": "В архиве",
}

STATUS_CSS = {
    "uploaded": "status-neutral",
    "queued": "status-info",
    "processing": "status-info",
    "processed": "status-success",
    "validated": "status-success",
    "failed": "status-error",
    "archived": "status-neutral",
}


def status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def status_class(status: str) -> str:
    return STATUS_CSS.get(status, "status-neutral")


def format_date(value: date | datetime | None) -> str:
    if value is None:
        return "—"
    if isinstance(value, datetime):
        return value.strftime("%d.%m.%Y %H:%M")
    return value.strftime("%d.%m.%Y")


def format_size(size_bytes: int) -> str:
    if size_bytes < 1024:
        return f"{size_bytes} Б"
    if size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} КБ"
    return f"{size_bytes / (1024 * 1024):.1f} МБ"


ROLE_LABELS = {
    "admin": "Администратор",
    "employee": "Сотрудник",
}

SECTION_ACCESS_ERROR_LABELS = {
    "invalid_section_access": "Недопустимый уровень доступа к разделу",
    "section_access_denied": "Нет доступа к этому разделу",
    "section_upload_denied": "Нет права на загрузку в этот раздел",
    "section_download_denied": "Нет права на скачивание из этого раздела",
    "section_links_denied": "Связи документов доступны при полном доступе или праве загрузки в раздел",
    "ai_access_denied": "AI доступен при праве загрузки и скачивания или «Полном доступе»",
    "ai_quota_exceeded": "Лимит AI-запросов на этот месяц исчерпан",
    "llm_not_configured": "AI не настроен: укажите YANDEX_API_KEY и YANDEX_FOLDER_ID в .env",
    "llm_timeout": "AI не ответил вовремя, попробуйте короче сформулировать вопрос",
    "llm_api_error": "Ошибка Yandex Cloud AI, проверьте ключ и каталог",
    "empty_question": "Введите вопрос",
}

USER_ERROR_LABELS = {
    "email_taken": "Пользователь с таким email уже существует",
    "invalid_email": "Укажите корректный email",
    "invalid_full_name": "Укажите имя пользователя",
    "invalid_password": "Пароль: минимум 8 символов, обязательны буквы и цифры",
    "password_too_short": "Пароль должен быть не короче 8 символов",
    "password_needs_letter_and_digit": "Пароль должен содержать буквы и цифры",
    "invalid_role": "Недопустимая роль",
    "self_demote_forbidden": "Нельзя снять с себя роль администратора",
    "self_deactivate_forbidden": "Нельзя деактивировать свой аккаунт",
    "user_not_found": "Пользователь не найден",
    **SECTION_ACCESS_ERROR_LABELS,
}


def role_label(role: str) -> str:
    return ROLE_LABELS.get(role, role)


def user_error_label(code: str | None) -> str:
    if not code:
        return "Произошла ошибка"
    return USER_ERROR_LABELS.get(code, "Произошла ошибка")
