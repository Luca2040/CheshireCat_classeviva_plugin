from cat.mad_hatter.decorators import tool, hook, plugin
from pydantic import BaseModel, Field

from datetime import datetime
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


def read_db(number, path):
    connection = sqlite3.connect(path)
    db_cursor = connection.cursor()

    db_cursor.execute(
        """SELECT count(name) FROM sqlite_master WHERE type='table' AND name='circolari' """
    )
    if db_cursor.fetchone()[0] == 0:
        db_cursor.execute("CREATE TABLE circolari(name, date, hash, text)")

    db_text_col = db_cursor.execute(
        f"SELECT text FROM circolari ORDER BY date DESC LIMIT {number}"
    ).fetchall()
    db_text = [value[0] for value in db_text_col]

    #db_number_col = db_cursor.execute(
    #    f"SELECT text FROM circolari ORDER BY number DESC LIMIT {number}"
    #).fetchall()
    #db_number = [value[0] for value in db_number_col]

    connection.commit()
    connection.close()

    returnString = ""

    for text in db_text:
        returnString += "Circolare n. {}\n"
        returnString += text
        returnString += "\n"

    return returnString


@tool
def numberToRead(number, cat):
    """
    Quante circolari devo riassumere? Input è il numero di circolari da analizzare.
    Riassumi le ultime circolari. Input è 5

    Esempio: Riassumi le ultime tre circolari.
    Input -> 3

    Esempio: Riassumi le ultime circolari.
    Input -> 5
    """

    settings = cat.mad_hatter.get_plugin().load_settings()
    path = settings["db_path"]

    db_text = read_db(number, path)

    return db_text
