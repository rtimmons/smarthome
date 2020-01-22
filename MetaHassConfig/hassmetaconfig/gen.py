import os
import yaml

import typing as typ


class MetaConfig:
    def __init__(self, fpath: str):
        self.fpath = fpath
        if not os.path.isfile(self.fpath):
            raise Exception(f"MetaConfig input {self.fpath} isn't a file")
        with open(fpath) as conts:
            self.data = yaml.load(conts, Loader=yaml.FullLoader)


class Automation:
    def __init__(self, metaconfig: MetaConfig):
        self.metaconfig = metaconfig

    def gen(self) -> typ.List[typ.Dict]:
        return []
