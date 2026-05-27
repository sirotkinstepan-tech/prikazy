def test_list_document_sections(client):
    response = client.get("/sections")

    assert response.status_code == 200
    payload = response.json()
    slugs = [item["slug"] for item in payload["items"]]
    labels = {item["slug"]: item["label"] for item in payload["items"]}

    assert slugs == ["prikaz", "internal_contract", "external_contract", "lna"]
    assert labels["prikaz"] == "Приказы"
    assert labels["internal_contract"] == "Договоры внутренние"
    assert labels["external_contract"] == "Договоры внешние"
    assert labels["lna"] == "ЛНА"
