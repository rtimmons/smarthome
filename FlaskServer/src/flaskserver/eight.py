import asyncio
from pyeight import eight

from flaskserver.vault import Vault


async def main8():
    loop = asyncio.get_running_loop()

    vault = Vault()

    api = eight.EightSleep(
        email=vault.decrypt("eight_user"),
        password=vault.decrypt("eight_pw"),
        tzone="America/New_York",
        partner=False,
        loop=loop,
    )
    if not await api.start():
        raise Exception("Couldn't auth")
    await api.assign_users()

    left: eight.EightUser = list(api.users.values())[0]
    await left.set_heating_level(-70)

    await api.stop()


asyncio.run(main8())
