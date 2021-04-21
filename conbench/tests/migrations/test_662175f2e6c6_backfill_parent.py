import datetime
import os

from alembic import command
from alembic.config import Config

from ...db import Session
from ...entities.commit import Commit


this_dir = os.path.abspath(os.path.dirname(__file__))
config_path = os.path.join(this_dir, "../../../alembic.ini")


def test_upgrade():
    repository = "https://github.com/apache/arrow"
    github = {
        "parent": "4beb514d071c9beec69b8917b5265e77ade22fb3",
        "message": f"ARROW-12429: [C++] Fix incorrectly registered test",
        "date": datetime.datetime(2021, 4, 17, 14, 25, 26),
        "author_name": "David Li",
        "author_login": "lidavidm",
        "author_avatar": "https://avatars.githubusercontent.com/u/327919?v=4",
    }
    commit_1 = Commit.create(
        {
            "sha": "fdd6ab11a71d4c40b4d24afa8458fed3d4589980",
            "repository": repository,
            "timestamp": github["date"],
            "message": github["message"],
            "author_name": github["author_name"],
            "author_login": github["author_login"],
            "author_avatar": github["author_avatar"],
        }
    )
    github = {
        "parent": "66aa3e7c365a8d4c4eca6e23668f2988e714b493",
        "message": f"ARROW-12421: [Rust] [DataFusion] Disable repartition rule",
        "date": datetime.datetime(2021, 4, 16, 17, 14, 16),
        "author_name": "Andy Grove",
        "author_login": "andygrove",
        "author_avatar": "https://avatars.githubusercontent.com/u/934084?v=4",
    }
    commit_2 = Commit.create(
        {
            "sha": "9c1e5bd19347635ea9f373bcf93f2cea0231d50a",
            "repository": repository,
            "parent": github["parent"],
            "timestamp": github["date"],
            "message": github["message"],
            "author_name": github["author_name"],
            "author_login": github["author_login"],
            "author_avatar": github["author_avatar"],
        }
    )

    # assert before migration
    assert commit_1.sha == "fdd6ab11a71d4c40b4d24afa8458fed3d4589980"
    assert commit_1.parent is None
    assert commit_1.author_name == "David Li"
    assert commit_2.sha == "9c1e5bd19347635ea9f373bcf93f2cea0231d50a"
    assert commit_2.parent == "66aa3e7c365a8d4c4eca6e23668f2988e714b493"
    assert commit_2.author_name == "Andy Grove"

    alembic_config = Config(config_path)
    command.stamp(alembic_config, "782f4533db71")
    command.upgrade(alembic_config, "662175f2e6c6")

    Session.refresh(commit_1)
    Session.refresh(commit_2)

    # assert after migration
    assert commit_1.sha == "fdd6ab11a71d4c40b4d24afa8458fed3d4589980"
    assert commit_1.parent == "9c1e5bd19347635ea9f373bcf93f2cea0231d50a"
    assert commit_1.author_name == "David Li"
    assert commit_2.sha == "9c1e5bd19347635ea9f373bcf93f2cea0231d50a"
    assert commit_2.parent == "66aa3e7c365a8d4c4eca6e23668f2988e714b493"
    assert commit_2.author_name == "Andy Grove"
