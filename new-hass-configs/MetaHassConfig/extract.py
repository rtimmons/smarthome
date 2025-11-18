import yaml

with open("metaconfig.yaml") as h:
    mc = yaml.safe_load(h)

ents = mc["entities"]
for ent in ents:
    if "node_id" not in ent:
        continue
    node_id = ent["node_id"]
    name = ent["name"]
    ntype = ent["type"]
    print(f"{name},{node_id},{ntype}")

