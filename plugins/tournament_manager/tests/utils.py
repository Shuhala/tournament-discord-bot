import json


def load_resource(filename: str):
    with open(f"plugins/tournament_manager/tests/resources/{filename}") as f:
        return json.load(f)
