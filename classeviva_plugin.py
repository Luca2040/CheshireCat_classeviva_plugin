from cat.mad_hatter.decorators import tool, hook, plugin
from pydantic import BaseModel, Field
from cat.looking_glass.cheshire_cat import CheshireCat
from numpy import dot
from numpy.linalg import norm
import pickle
import sqlite3


class MySettings(BaseModel):
    db_path: str = Field(
        default="/app/cat/database/circolari.db",
        title="SQLite database path",
    )


@plugin
def settings_schema():
    return MySettings.model_json_schema()


@hook
def agent_prompt_prefix(prefix, cat):

    prefix = """Aiuti le persone a guardare gli argomenti delle circolari del registro classeviva.
    Le tue risposte devono essere complete e devono contenere tutte le informazioni importanti contenute nelle circolari, scrivendo in elenco puntato un riassunto completo per ogni circolare.
    Devi specificare il contenuto di ogni circolare, il suo numero indicato in (Circolare n.) e il suo nome, le tue risposte devono essere lunghe.
    """

    return prefix


##---------- TEST ----------
# @hook
# def before_cat_reads_message(user_message_json, cat: CheshireCat):
#    settings = cat.mad_hatter.get_plugin().load_settings()
#    path = settings["db_path"]
#
#    connection = sqlite3.connect(path)
#    db_cursor = connection.cursor()
#
#    db_cursor.execute("SELECT text FROM circolari")
#    rows = db_cursor.fetchall()
#
#    rowtest = ""
#
#    for row in rows:
#        rowtest = rowtest + row[0]
#
#    emb_documents = cat.embedder.embed_documents([rowtest])
#
#    db_cursor.execute("SELECT name FROM circolari")
#    rows = db_cursor.fetchall()
#
#    query = cat.embedder.embed_query("Musica")
#
#    cos_sim = []
#
#    components = [(row[0], point) for (row, point) in zip(rows, emb_documents)]
#
#    for name, doc_point in components:
#
#        cos_sim.append((dot(query, doc_point) / (norm(query) * norm(doc_point)), name))
#
#    return user_message_json


@hook
def before_cat_reads_message(user_message_json, cat: CheshireCat):
    settings = cat.mad_hatter.get_plugin().load_settings()
    path = settings["db_path"]
    circ_table_name = "circolari"
    com_table_name = "comunicazioni"
    text_col_name = "text"
    hash_col_name = "hash"
    point_col_name = "point"

    update_points(
        cat,
        path=path,
        table_name=circ_table_name,
        text_col_name=text_col_name,
        hash_col_name=hash_col_name,
        point_col_name=point_col_name,
    )
    update_points(
        cat,
        path=path,
        table_name=com_table_name,
        text_col_name=text_col_name,
        hash_col_name=hash_col_name,
        point_col_name=point_col_name,
    )

    return user_message_json


def update_points(
    cat: CheshireCat, path, table_name, point_col_name, hash_col_name, text_col_name
):
    connection = sqlite3.connect(path)
    db_cursor = connection.cursor()

    new = read_new__hash(db_cursor, table_name, hash_col_name, point_col_name)

    if len(new) == 0:
        return

    for hash in new:
        text = get_text_at_hash(
            db_cursor, table_name, text_col_name, hash_col_name, hash
        )
        point = cat.embedder.embed_documents([text])  # TODO: divide text in parts

        serialized_point = pickle.dumps(point)

        db_cursor.execute(
            f"UPDATE {table_name} SET {point_col_name} = ? WHERE {hash_col_name} = ?",
            (
                serialized_point,
                hash,
            ),
        )

    connection.commit()
    connection.close()


def get_text_at_hash(db_cursor, table_name, text_col_name, hash_col_name, hash):
    db_cursor.execute(
        f"SELECT {text_col_name} FROM {table_name} WHERE {hash_col_name} = ?", (hash,)
    )
    text = db_cursor.fetchone()

    if text:
        return text[0]
    else:
        raise None


def read_new__hash(db_cursor, table_name, hash_col_name, point_col_name):
    db_cursor.execute(
        f"SELECT {hash_col_name} FROM {table_name} WHERE {point_col_name} IS NULL"
    )
    hashes = db_cursor.fetchall()

    return [hash[0] for hash in hashes]


def read_last_db(number, path):
    connection = sqlite3.connect(path)
    db_cursor = connection.cursor()

    db_cursor.execute(
        """SELECT count(name) FROM sqlite_master WHERE type='table' AND name='circolari' """
    )
    if db_cursor.fetchone()[0] == 0:
        return ""

    db_text_col = db_cursor.execute(
        f"SELECT text FROM circolari ORDER BY date DESC LIMIT {number}"
    ).fetchall()
    db_text = [value[0] for value in db_text_col]

    connection.commit()
    connection.close()

    returnString = ""

    for text in db_text:
        returnString += f"\n\nCircolare n.{{}}:\n{{}} - {{}}\n{text}\n\n"#TODO: format the output

    return returnString


@tool
def read_latest_n(number, cat):
    """
    Quante circolari devo riassumere? Input è il numero di circolari da analizzare, solo se non viene fornito nessuno specifico argomento

    Riassumi le ultime circolari. Input è 5

    Esempio: Riassumi le ultime tre circolari.
    Input -> 3

    Esempio: Riassumi le ultime circolari.
    Input -> 5
    """

    settings = cat.mad_hatter.get_plugin().load_settings()
    path = settings["db_path"]

    db_text = read_last_db(number, path)

    return db_text


def get_points_from_table(db_cursor, table_name, point_col_name, hash_col_name):
    db_cursor.execute(f"SELECT {point_col_name},{hash_col_name} FROM {table_name}")
    return [
        (value[1], point)
        for value in db_cursor.fetchall()
        for point in pickle.loads(value[0])
    ]


def get_score_from_points(points, query):
    score = []

    for hash, point in points:
        score.append((hash, dot(query, point) / (norm(query) * norm(point))))

    return score


def get_n_max(numbers, score):
    sorted_score = sorted(score, key=lambda x: x[1], reverse=True)

    max_hashes = []

    for hash, score in sorted_score:
        if hash not in max_hashes:
            max_hashes.append(hash)

    return max_hashes[:numbers]


@tool
def read_this(input, cat):
    """
    Devo riassumere la circolare che parla di cosa? Input è l'argomento richiesto della circolare.

    Esempio: Riassumi la circolare che parla di gatti.
    Input -> "gatti"
    
    Esempio: Riassumi la circolare che parla del film da guardare in classe.
    Input -> "film da guardare in classe"
    """

    settings = cat.mad_hatter.get_plugin().load_settings()
    path = settings["db_path"]
    circ_table_name = "circolari"
    number_col_name = "number"
    name_col_name = "name"
    date_col_name = "date"
    hash_col_name = "hash"
    text_col_name = "text"
    point_col_name = "point"

    similarity_tolerance = 2

    connection = sqlite3.connect(path)
    db_cursor = connection.cursor()

    points = get_points_from_table(
        db_cursor, circ_table_name, point_col_name, hash_col_name
    )
    query = cat.embedder.embed_query(input)

    score = get_score_from_points(points, query)

    high_score_hashes = get_n_max(similarity_tolerance, score)

    return_text = ""

    for hash_ in high_score_hashes:
        number = get_text_at_hash(
            db_cursor, circ_table_name, number_col_name, hash_col_name, hash_
        )
        name = get_text_at_hash(
            db_cursor, circ_table_name, name_col_name, hash_col_name, hash_
        )
        date = get_text_at_hash(
            db_cursor, circ_table_name, date_col_name, hash_col_name, hash_
        )
        text = get_text_at_hash(
            db_cursor, circ_table_name, text_col_name, hash_col_name, hash_
        )

        circ_text = f"\n\nCircolare n.{number}:\n{name} - {date}\n{text}\n\n"

        return_text += circ_text

    return return_text
