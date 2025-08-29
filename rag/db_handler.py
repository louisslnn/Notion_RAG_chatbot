def read_and_save_ids(file='pages_id.txt'):
    ids = []

    with open(file=file, encoding='utf-8') as f:
        text = f.read()

    for line in text.split("\n"):
        if line.strip():   # skip empty lines
            ids.append(line.strip())

    return ids


def add_pages_to_db(db, pages):
    pass
