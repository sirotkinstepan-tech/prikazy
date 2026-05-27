from urllib.parse import quote


def build_content_disposition(disposition: str, filename: str) -> str:
    safe_filename = filename.replace('"', "'").replace("\r", "").replace("\n", "")
    encoded = quote(safe_filename)
    ascii_filename = safe_filename.encode("latin-1", errors="replace").decode("latin-1")
    return f'{disposition}; filename="{ascii_filename}"; filename*=UTF-8\'\'{encoded}'
