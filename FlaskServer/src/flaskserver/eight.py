import asyncio
from pyeight import eight

from flaskserver.vault import Vault


async def main(key):
    loop = asyncio.get_running_loop()

    vault = Vault(key)

    api = eight.EightSleep(
        email="ryan@rytim.com",
        password=vault.decrypt("eight"),
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


# asyncio.run(main(KEY))
