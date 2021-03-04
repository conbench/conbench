import dateutil.parser


def parse_commit(commit):
    return {
        "url": commit["html_url"],
        "date": dateutil.parser.isoparse(commit["commit"]["author"]["date"]),
        "message": commit["commit"]["message"].split("\n")[0],
        "author_name": commit["commit"]["author"]["name"],
        "author_login": commit["author"]["login"],
        "author_avatar": commit["author"]["avatar_url"],
    }
