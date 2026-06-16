def already_sent_saldo(db, day: str) -> bool:
    return db.get_state("saldo_date") == day


def mark_saldo_sent(db, day: str):
    db.set_state("saldo_date", day)


def already_prompted_checkin(db, day: str) -> bool:
    return db.get_state("checkin_date") == day


def mark_checkin_prompted(db, day: str):
    db.set_state("checkin_date", day)
