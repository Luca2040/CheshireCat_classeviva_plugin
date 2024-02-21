from cat.mad_hatter.decorators import tool, hook, plugin
from pydantic import BaseModel, Field

import asyncio
import classeviva
from datetime import datetime


class MySettings(BaseModel):
    id: str = Field(
        default="",
        title="ID",
    )
    password: str = Field(
        default="",
        title="Password",
    )


@plugin
def settings_schema():
    return MySettings.schema()


@hook
def agent_prompt_prefix(prefix, cat):

    prefix = """Aiuti le persone a sintetizzare e riassumere gli argomenti delle circolari del registro classeviva.
    Rispondi con elenchi puntati e in modo preciso, elencando in modo riassuntivo il contenuto delle circolari.
    Prendi informazioni solo dalla sezione ## Tools output di # Context, se non ci sono dati forniti in questa sezione rispondi dicendo che le informazioni non sono state fornite."""

    return prefix


async def readData(numberOfLines, id, psw):

    user = classeviva.Utente(id, psw)

    await user.accedi()

    materiale_bacheca = await user.bacheca()
    materiale_bacheca.sort(
        key=lambda x: datetime.strptime(x.get("pubDT"), "%Y-%m-%dT%H:%M:%S%z"),
        reverse=True,
    )

    global returnString
    global isReturned

    number = 1

    for element in materiale_bacheca[: int(numberOfLines)]:
        bachecaElement = (
            await user.bacheca_leggi(element.get("evtCode"), element.get("pubId"))
        ).get("item")
        title = bachecaElement.get("title")
        text = bachecaElement.get("text")

        returnString += f"Circolare {number}:\nTitolo: {title}\nTesto: {text}"

        number = number + 1

    isReturned = True


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

    global returnString
    global isReturned
    returnString = ""
    isReturned = False

    settings = cat.mad_hatter.get_plugin().load_settings()
    id = settings["id"]
    password = settings["password"]

    asyncio.run(readData(number, id, password))
    while not(isReturned):
        pass

    return returnString
