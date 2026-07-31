import time

from app.db import DAY, Database


def test_add_user_and_duplicates(db):
    assert db.add_user(1, "alice", 7) is True
    assert db.add_user(1, "alice", 7) is False
    row = db.get_user(1)
    assert row["username"] == "alice"
    assert row["paid_until"] > time.time() + 6 * DAY


def test_get_missing_user(db):
    assert db.get_user(404) is None


def test_delete_user(db):
    db.add_user(1, "a", 7)
    db.add_keywords(1, ["python"])
    db.delete_user(1)
    assert db.get_user(1) is None
    assert db.keywords(1) == []


def test_active_and_pause(db):
    db.add_user(1, "a", 7)
    assert len(db.active_users()) == 1
    db.set_active(1, False)
    assert len(db.active_users()) == 0
    db.set_active(1, True)
    assert db.stats() == {"users": 1, "active": 1}


def test_subscription_expiry_and_grant(db):
    db.add_user(1, "a", 0)  # zero test days -> expired immediately
    assert db.is_subscribed(1) is False
    db.grant_days(1, 30)
    assert db.is_subscribed(1) is True


def test_grant_days_extends_future_subscription(db):
    db.add_user(1, "a", 10)
    before = db.get_user(1)["paid_until"]
    assert db.grant_days(1, 5) == before + 5 * DAY


def test_grant_days_unknown_user_starts_from_now(db):
    paid_until = db.grant_days(99, 1)
    assert paid_until > time.time()


def test_is_subscribed_unknown_user(db):
    assert db.is_subscribed(12345) is False


def test_keywords_crud(db):
    assert db.add_keywords(1, [" Python ", "python", "", "django"]) == 2
    assert db.keywords(1) == ["django", "python"]
    assert db.del_keyword(1, "PYTHON ") is True
    assert db.del_keyword(1, "python") is False


def test_site_toggle_default_enabled(db):
    assert db.site_enabled(1, "fl_ru") is True
    assert db.toggle_site(1, "fl_ru") is False
    assert db.site_enabled(1, "fl_ru") is False
    assert db.toggle_site(1, "fl_ru") is True
    assert db.site_enabled(1, "fl_ru") is True


def test_mark_sent_dedupe_and_purge(db):
    assert db.mark_sent(1, "fl_ru:1") is True
    assert db.mark_sent(1, "fl_ru:1") is False
    db.conn.execute("UPDATE sent SET sent_at = sent_at - ?", (40 * DAY,))
    assert db.purge_sent(30) == 1


def test_db_file_path(tmp_path):
    database = Database(str(tmp_path / "sub" / "db.sqlite3"))
    database.add_user(1, "a", 1)
    database.close()
    assert (tmp_path / "sub" / "db.sqlite3").exists()
