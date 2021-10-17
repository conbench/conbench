from ...app._util import display_message


def test_truncate_commit_shas_in_message():
    message = "Nothing to change here"
    expected = "Nothing to change here"
    assert display_message(message) == expected

    message = "Merge 2d642d9cb3d2bf06815e8c30ec10df1566ee04c0 into 9b0b52ece6e81aac699d14d48b6dbadf6e8d52e0"
    expected = "Merge 2d642d9 into 9b0b52e"
    assert display_message(message) == expected
