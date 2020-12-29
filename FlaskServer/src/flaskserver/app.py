import asyncio
import inspect
import atexit
import signal

from flask import Flask, request
from pyeight import eight

from flaskserver.vault import Vault

app = Flask(__name__)
loop = asyncio.get_event_loop()

vault = Vault()

api = eight.EightSleep(
    email=vault.decrypt("eight_user"),
    password=vault.decrypt("eight_pw"),
    tzone="America/New_York",
    partner=False,
    loop=loop,
)

STARTED = False


async def start():
    global STARTED
    if STARTED:
        return
    if not await api.start():
        raise Exception("Couldn't auth")
    STARTED = True


# def stop(*args):
#     global STARTED
#     print(f"Started stop {args}")
#     if STARTED is True:
#         print("Running api.stop()")
#         loop.run_until_complete(api.stop())
#         STARTED = False
#         print("Finished api.stop()")
# signal.signal(signal.SIGINT, stop)


async def set_left(to_val):
    await start()
    await api.assign_users()
    left: eight.EightUser = list(api.users.values())[0]
    print(f"Current target is {inspect.getmembers(left.target_heating_level)}")
    await left.set_heating_level(to_val)


@app.route("/set-left")
def route_set():
    to_val = int(request.args.get("to-val"))
    loop.run_until_complete(set_left(to_val))
    return f"Set left to {to_val}"


# TODO:
#     await api.stop()

# env FLASK_APP=hello.py flask run
