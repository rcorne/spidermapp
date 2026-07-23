from spidermapp.core import tasks


def test_new_task_defaults():
    t = tasks.new_task("Arreglar 404s", site="ejemplo.cl")
    assert t.title == "Arreglar 404s"
    assert t.site == "ejemplo.cl"
    assert t.status == tasks.DEFAULT_STATUS
    assert t.impact == "medio"
    assert t.id


def test_new_task_rejects_invalid_impact_by_falling_back():
    t = tasks.new_task("x", impact="catastrofico")
    assert t.impact == "medio"


def test_add_and_find_task():
    t = tasks.new_task("Tarea 1")
    result = tasks.add_task([], t)
    assert len(result) == 1
    assert tasks.find_task(result, t.id) is t


def test_delete_task():
    t1, t2 = tasks.new_task("A"), tasks.new_task("B")
    result = tasks.delete_task([t1, t2], t1.id)
    assert result == [t2]


def test_set_status_updates_task_in_place():
    t = tasks.new_task("A")
    result = tasks.set_status([t], t.id, "En progreso")
    assert result[0].status == "En progreso"


def test_set_status_rejects_unknown_status():
    t = tasks.new_task("A")
    try:
        tasks.set_status([t], t.id, "Cancelada")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_set_status_no_op_for_unknown_task_id():
    t = tasks.new_task("A")
    result = tasks.set_status([t], "does-not-exist", "Hecho")
    assert result[0].status == tasks.DEFAULT_STATUS


def test_add_comment():
    t = tasks.new_task("A")
    tasks.add_comment([t], t.id, "Rodrigo", "¿Ya revisamos esto?")
    assert len(t.comments) == 1
    assert t.comments[0].author == "Rodrigo"
    assert t.comments[0].text == "¿Ya revisamos esto?"


def test_add_comment_ignores_blank_text():
    t = tasks.new_task("A")
    tasks.add_comment([t], t.id, "Rodrigo", "   ")
    assert t.comments == []


def test_add_comment_defaults_author_when_blank():
    t = tasks.new_task("A")
    tasks.add_comment([t], t.id, "", "hola")
    assert t.comments[0].author == "Anónimo"


def test_checklist_add_and_toggle():
    t = tasks.new_task("A")
    tasks.add_checklist_item([t], t.id, "Identificar URLs")
    assert len(t.checklist) == 1
    assert t.checklist[0].done is False
    tasks.toggle_checklist_item([t], t.id, 0)
    assert t.checklist[0].done is True
    tasks.toggle_checklist_item([t], t.id, 0)
    assert t.checklist[0].done is False


def test_toggle_checklist_item_out_of_range_is_noop():
    t = tasks.new_task("A")
    tasks.toggle_checklist_item([t], t.id, 5)  # no checklist items at all
    assert t.checklist == []


def test_tasks_by_status_groups_and_keeps_empty_buckets():
    t1 = tasks.new_task("A")
    t2 = tasks.new_task("B")
    tasks.set_status([t1, t2], t2.id, "Hecho")
    buckets = tasks.tasks_by_status([t1, t2])
    assert buckets["Por hacer"] == [t1]
    assert buckets["Hecho"] == [t2]
    assert buckets["En progreso"] == []


def test_save_and_load_tasks_roundtrip(tmp_path):
    path = tmp_path / "tasks.json"
    t = tasks.new_task("Arreglar 404s", site="ejemplo.cl", impact="alto", labels=["Técnico"])
    tasks.add_checklist_item([t], t.id, "Paso 1")
    tasks.add_comment([t], t.id, "Ana", "Buen hallazgo")
    tasks.save_tasks([t], path)

    loaded = tasks.load_tasks(path)
    assert len(loaded) == 1
    reloaded = loaded[0]
    assert reloaded.title == "Arreglar 404s"
    assert reloaded.site == "ejemplo.cl"
    assert reloaded.impact == "alto"
    assert reloaded.labels == ["Técnico"]
    assert reloaded.checklist[0].text == "Paso 1"
    assert reloaded.checklist[0].done is False
    assert reloaded.comments[0].author == "Ana"


def test_load_tasks_missing_file_returns_empty_list(tmp_path):
    assert tasks.load_tasks(tmp_path / "does_not_exist.json") == []


def test_load_tasks_corrupt_file_returns_empty_list(tmp_path):
    path = tmp_path / "corrupt.json"
    path.write_text("{not valid json")
    assert tasks.load_tasks(path) == []
