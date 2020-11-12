# Copyright 2020 Canonical Ltd.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# For further info, check https://github.com/canonical/charmcraft

"""Tests for the Store commands (code in store/__init__.py)."""

import datetime
import hashlib
import logging
import os
import pathlib
from argparse import Namespace
from unittest.mock import patch, call, MagicMock

import pytest
import yaml
from dateutil import parser

from charmcraft.cmdbase import CommandError
from charmcraft.commands.store import (
    _get_lib_info,
    CreateLibCommand,
    ListNamesCommand,
    ListRevisionsCommand,
    LoginCommand,
    LogoutCommand,
    RegisterNameCommand,
    ReleaseCommand,
    StatusCommand,
    UploadCommand,
    WhoamiCommand,
    get_name_from_metadata,
)
from charmcraft.commands.store.store import (
    Channel,
    Charm,
    Error,
    Release,
    Revision,
    Uploaded,
    User,
)
from charmcraft.commands.utils import get_templates_environment
from tests import factory

# used a lot!
noargs = Namespace()


@pytest.fixture
def store_mock():
    """The fixture to fake the store layer in all the tests."""
    store_mock = MagicMock()
    with patch('charmcraft.commands.store.Store', lambda: store_mock):
        yield store_mock


# -- tests for helpers


def test_get_name_from_metadata_ok(tmp_path, monkeypatch):
    """The metadata file is valid yaml, but there is no name."""
    monkeypatch.chdir(tmp_path)

    # put a valid metadata
    metadata_file = tmp_path / 'metadata.yaml'
    with metadata_file.open('wb') as fh:
        fh.write(b"name: test-name")

    result = get_name_from_metadata()
    assert result == "test-name"


def test_get_name_from_metadata_no_file(tmp_path, monkeypatch):
    """No metadata file to get info."""
    monkeypatch.chdir(tmp_path)
    result = get_name_from_metadata()
    assert result is None


def test_get_name_from_metadata_bad_content_garbage(tmp_path, monkeypatch):
    """The metadata file is broken."""
    monkeypatch.chdir(tmp_path)

    # put a broken metadata
    metadata_file = tmp_path / 'metadata.yaml'
    with metadata_file.open('wb') as fh:
        fh.write(b"\b00\bff -- not a realy yaml stuff")

    result = get_name_from_metadata()
    assert result is None


def test_get_name_from_metadata_bad_content_no_name(tmp_path, monkeypatch):
    """The metadata file is valid yaml, but there is no name."""
    monkeypatch.chdir(tmp_path)

    # put a broken metadata
    metadata_file = tmp_path / 'metadata.yaml'
    with metadata_file.open('wb') as fh:
        fh.write(b"{}")

    result = get_name_from_metadata()
    assert result is None


# -- tests for auth commands


def test_login(caplog, store_mock):
    """Simple login case."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    LoginCommand('group').run(noargs)

    assert store_mock.mock_calls == [
        call.login(),
    ]
    assert ["Login successful."] == [rec.message for rec in caplog.records]


def test_logout(caplog, store_mock):
    """Simple logout case."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    LogoutCommand('group').run(noargs)

    assert store_mock.mock_calls == [
        call.logout(),
    ]
    assert ["Credentials cleared."] == [rec.message for rec in caplog.records]


def test_whoami(caplog, store_mock):
    """Simple whoami case."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = User(name='John Doe', username='jdoe', userid='-1')
    store_mock.whoami.return_value = store_response

    WhoamiCommand('group').run(noargs)

    assert store_mock.mock_calls == [
        call.whoami(),
    ]
    expected = [
        'name:      John Doe',
        'username:  jdoe',
        'id:        -1',
    ]
    assert expected == [rec.message for rec in caplog.records]


# -- tests for name-related commands


def test_register_name(caplog, store_mock):
    """Simple register_name case."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    args = Namespace(name='testname')
    RegisterNameCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.register_name('testname'),
    ]
    expected = "Congrats! You are now the publisher of 'testname'."
    assert [expected] == [rec.message for rec in caplog.records]


def test_list_registered_empty(caplog, store_mock):
    """List registered with empty response."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = []
    store_mock.list_registered_names.return_value = store_response

    ListNamesCommand('group').run(noargs)

    assert store_mock.mock_calls == [
        call.list_registered_names(),
    ]
    expected = "Nothing found."
    assert [expected] == [rec.message for rec in caplog.records]


def test_list_registered_one_private(caplog, store_mock):
    """List registered with one private item in the response."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = [
        Charm(name='charm', private=True, status='status'),
    ]
    store_mock.list_registered_names.return_value = store_response

    ListNamesCommand('group').run(noargs)

    assert store_mock.mock_calls == [
        call.list_registered_names(),
    ]
    expected = [
        "Name    Visibility    Status",
        "charm   private       status",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_list_registered_one_public(caplog, store_mock):
    """List registered with one public item in the response."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = [
        Charm(name='charm', private=False, status='status'),
    ]
    store_mock.list_registered_names.return_value = store_response

    ListNamesCommand('group').run(noargs)

    assert store_mock.mock_calls == [
        call.list_registered_names(),
    ]
    expected = [
        "Name    Visibility    Status",
        "charm   public        status",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_list_registered_several(caplog, store_mock):
    """List registered with several itemsssssssss in the response."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = [
        Charm(name='charm1', private=True, status='simple status'),
        Charm(name='charm2-long-name', private=False, status='other'),
        Charm(name='charm3', private=True, status='super long status'),
    ]
    store_mock.list_registered_names.return_value = store_response

    ListNamesCommand('group').run(noargs)

    assert store_mock.mock_calls == [
        call.list_registered_names(),
    ]
    expected = [
        "Name              Visibility    Status",
        "charm1            private       simple status",
        "charm2-long-name  public        other",
        "charm3            private       super long status",
    ]
    assert expected == [rec.message for rec in caplog.records]


# -- tests for upload command


def test_upload_call_ok(caplog, store_mock):
    """Simple upload, success result."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = Uploaded(ok=True, status=200, revision=7)
    store_mock.upload.return_value = store_response

    args = Namespace(charm_file='whatever-cmd-arg')
    with patch('charmcraft.commands.store.UploadCommand._discover_charm') as mock_discover:
        mock_discover.return_value = ('discovered-name', 'discovered-path')
        UploadCommand('group').run(args)

    # check it called self discover helper with correct args
    mock_discover.assert_called_once_with('whatever-cmd-arg')

    assert store_mock.mock_calls == [
        call.upload('discovered-name', 'discovered-path')
    ]
    expected = "Revision 7 of 'discovered-name' created"
    assert [expected] == [rec.message for rec in caplog.records]


def test_upload_call_error(caplog, store_mock):
    """Simple upload but with a response indicating an error."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = Uploaded(ok=False, status=400, revision=None)
    store_mock.upload.return_value = store_response

    args = Namespace(charm_file='whatever-cmd-arg')
    with patch('charmcraft.commands.store.UploadCommand._discover_charm') as mock_discover:
        mock_discover.return_value = ('discovered-name', 'discovered-path')
        UploadCommand('group').run(args)

    expected = "Upload failed: got status 400"
    assert [expected] == [rec.message for rec in caplog.records]


def test_upload_discover_pathgiven_ok(tmp_path):
    """Discover charm name/path, indicated path ok."""
    charm_file = tmp_path / 'testfile.charm'
    charm_file.touch()

    name, path = UploadCommand('group')._discover_charm(charm_file)
    assert name == 'testfile'
    assert path == charm_file


def test_upload_discover_pathgiven_home_expanded(tmp_path):
    """Discover charm name/path, home-expand the indicated path."""
    fake_home = tmp_path / 'homedir'
    fake_home.mkdir()
    charm_file = fake_home / 'testfile.charm'
    charm_file.touch()

    with patch.dict(os.environ, {'HOME': str(fake_home)}):
        name, path = UploadCommand('group')._discover_charm(pathlib.Path('~/testfile.charm'))
    assert name == 'testfile'
    assert path == charm_file


def test_upload_discover_pathgiven_missing(tmp_path):
    """Discover charm name/path, the indicated path is not there."""
    with pytest.raises(CommandError) as cm:
        UploadCommand('group')._discover_charm(pathlib.Path('not_really_there.charm'))
    assert str(cm.value) == "Can't access the indicated charm file: 'not_really_there.charm'"


def test_upload_discover_pathgiven_not_a_file(tmp_path):
    """Discover charm name/path, the indicated path is not a file."""
    with pytest.raises(CommandError) as cm:
        UploadCommand('group')._discover_charm(tmp_path)
    assert str(cm.value) == "The indicated charm is not a file: {!r}".format(str(tmp_path))


def test_upload_discover_default_ok(tmp_path, monkeypatch):
    """Discover charm name/path, default to get info from metadata, ok."""
    monkeypatch.chdir(tmp_path)

    # touch the charm file
    charm_file = tmp_path / 'testcharm.charm'
    charm_file.touch()

    # fake the metadata to point to that file
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = 'testcharm'

        name, path = UploadCommand('group')._discover_charm(None)

    assert name == 'testcharm'
    assert path == charm_file


def test_upload_discover_default_no_metadata(tmp_path):
    """Discover charm name/path, no metadata file to get info."""
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = None

        with pytest.raises(CommandError) as cm:
            UploadCommand('group')._discover_charm(None)

    assert str(cm.value) == (
        "Can't access name in 'metadata.yaml' file. The 'upload' command needs to be executed in "
        "a valid project's directory, or point to a charm file with the --charm-file option.")


def test_upload_discover_default_no_charm_file(tmp_path, monkeypatch):
    """Discover charm name/path, the metadata indicates a not accesible."""
    monkeypatch.chdir(tmp_path)

    # fake the metadata to point to a missing file
    metadata_data = {'name': 'testcharm'}
    metadata_file = tmp_path / 'metadata.yaml'
    metadata_raw = yaml.dump(metadata_data).encode('ascii')
    with metadata_file.open('wb') as fh:
        fh.write(metadata_raw)

    with pytest.raises(CommandError) as cm:
        UploadCommand('group')._discover_charm(None)
    assert str(cm.value) == (
        "Can't access charm file {!r}. You can indicate a charm file with "
        "the --charm-file option.".format(str(tmp_path / 'testcharm.charm')))


# -- tests for list revisions command


def test_revisions_simple(caplog, store_mock):
    """Happy path of one result from the Store."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = [
        Revision(
            revision=1, version='v1', created_at=datetime.datetime(2020, 7, 3, 20, 30, 40),
            status='accepted', errors=[]),
    ]
    store_mock.list_revisions.return_value = store_response

    args = Namespace(name='testcharm')
    ListRevisionsCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_revisions('testcharm'),
    ]
    expected = [
        "Revision    Version    Created at    Status",
        "1           v1         2020-07-03    accepted",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_revisions_name_from_metadata_ok(store_mock):
    """The charm name is retrieved succesfully from the metadata."""
    store_mock.list_revisions.return_value = []
    args = Namespace(name=None)
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = 'test-name'
        ListRevisionsCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_revisions('test-name'),
    ]


def test_revisions_name_from_metadata_problem(store_mock):
    """The metadata wasn't there to get the name."""
    args = Namespace(name=None)
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = None
        with pytest.raises(CommandError) as cm:
            ListRevisionsCommand('group').run(args)
        assert str(cm.value) == (
            "Can't access name in 'metadata.yaml' file. The 'revisions' command needs to "
            "be executed in a valid project's directory, or indicate the charm name with "
            "the --name option.")


def test_revisions_empty(caplog, store_mock):
    """No results from the store."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = []
    store_mock.list_revisions.return_value = store_response

    args = Namespace(name='testcharm')
    ListRevisionsCommand('group').run(args)

    expected = [
        "Nothing found",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_revisions_ordered_by_revision(caplog, store_mock):
    """Results are presented ordered by revision in the table."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    # three Revisions with all values weirdly similar, the only difference is revision, so
    # we really assert later that it was used for ordering
    tstamp = datetime.datetime(2020, 7, 3, 20, 30, 40)
    store_response = [
        Revision(revision=1, version='v1', created_at=tstamp, status='accepted', errors=[]),
        Revision(revision=3, version='v1', created_at=tstamp, status='accepted', errors=[]),
        Revision(revision=2, version='v1', created_at=tstamp, status='accepted', errors=[]),
    ]
    store_mock.list_revisions.return_value = store_response

    args = Namespace(name='testcharm')
    ListRevisionsCommand('group').run(args)

    expected = [
        "Revision    Version    Created at    Status",
        "3           v1         2020-07-03    accepted",
        "2           v1         2020-07-03    accepted",
        "1           v1         2020-07-03    accepted",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_revisions_version_null(caplog, store_mock):
    """Support the case of version being None."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = [
        Revision(
            revision=1, version=None, created_at=datetime.datetime(2020, 7, 3, 20, 30, 40),
            status='accepted', errors=[]),
    ]
    store_mock.list_revisions.return_value = store_response

    args = Namespace(name='testcharm')
    ListRevisionsCommand('group').run(args)

    expected = [
        "Revision    Version    Created at    Status",
        "1                      2020-07-03    accepted",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_revisions_errors_simple(caplog, store_mock):
    """Support having one case with a simple error."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = [
        Revision(
            revision=1, version=None, created_at=datetime.datetime(2020, 7, 3, 20, 30, 40),
            status='rejected', errors=[Error(message="error text", code='broken')]),
    ]
    store_mock.list_revisions.return_value = store_response

    args = Namespace(name='testcharm')
    ListRevisionsCommand('group').run(args)

    expected = [
        "Revision    Version    Created at    Status",
        "1                      2020-07-03    rejected: error text [broken]",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_revisions_errors_multiple(caplog, store_mock):
    """Support having one case with multiple errors."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_response = [
        Revision(
            revision=1, version=None, created_at=datetime.datetime(2020, 7, 3, 20, 30, 40),
            status='rejected', errors=[
                Error(message="text 1", code='missing-stuff'),
                Error(message="other long error text", code='broken'),
            ]),
    ]
    store_mock.list_revisions.return_value = store_response

    args = Namespace(name='testcharm')
    ListRevisionsCommand('group').run(args)

    expected = [
        "Revision    Version    Created at    Status",
        "1                      2020-07-03    rejected: text 1 [missing-stuff]; other long error text [broken]",  # NOQA
    ]
    assert expected == [rec.message for rec in caplog.records]


# -- tests for the release command


def test_release_simple_ok(caplog, store_mock):
    """Simple case of releasing a revision ok."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    channels = ['somechannel']
    args = Namespace(name='testcharm', revision=7, channels=channels)
    ReleaseCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.release('testcharm', 7, channels),
    ]

    expected = "Revision 7 of charm 'testcharm' released to somechannel"
    assert [expected] == [rec.message for rec in caplog.records]


def test_release_simple_multiple_channels(caplog, store_mock):
    """Releasing to multiple channels."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    args = Namespace(name='testcharm', revision=7, channels=['channel1', 'channel2', 'channel3'])
    ReleaseCommand('group').run(args)

    expected = "Revision 7 of charm 'testcharm' released to channel1, channel2, channel3"
    assert [expected] == [rec.message for rec in caplog.records]


def test_release_name_guessing_ok(caplog, store_mock):
    """Release after guessing the charm's name correctly."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    args = Namespace(name=None, revision=7, channels=['somechannel'])
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = 'guessed-name'
        ReleaseCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.release('guessed-name', 7, ['somechannel']),
    ]
    expected = "Revision 7 of charm 'guessed-name' released to somechannel"
    assert [expected] == [rec.message for rec in caplog.records]


def test_release_name_guessing_bad():
    """The charm name couldn't be guessed."""
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = None

        args = Namespace(name=None, revision=7, channels=['somechannel'])
        with pytest.raises(CommandError) as cm:
            ReleaseCommand('group').run(args)

        assert str(cm.value) == (
            "Can't access name in 'metadata.yaml' file. The 'release' command needs to "
            "be executed in a valid project's directory, or indicate the charm name with "
            "the --name option.")


# -- tests for the status command

def _build_channels(track='latest'):
    """Helper to build simple channels structure."""
    channels = []
    risks = ['stable', 'candidate', 'beta', 'edge']
    for risk, fback in zip(risks, [None] + risks):
        name = "/".join((track, risk))
        fallback = None if fback is None else "/".join((track, fback))
        channels.append(Channel(name=name, fallback=fallback, track=track, risk=risk, branch=None))
    return channels


def _build_revision(revno, version):
    """Helper to build a revision."""
    return Revision(
        revision=revno, version=version, created_at=datetime.datetime(2020, 7, 3, 20, 30, 40),
        status='accepted', errors=[])


def test_status_simple_ok(caplog, store_mock):
    """Simple happy case of getting a status."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    channel_map = [
        Release(revision=7, channel='latest/stable', expires_at=None),
        Release(revision=7, channel='latest/candidate', expires_at=None),
        Release(revision=80, channel='latest/beta', expires_at=None),
        Release(revision=156, channel='latest/edge', expires_at=None),
    ]
    channels = _build_channels()
    revisions = [
        _build_revision(revno=7, version='v7'),
        _build_revision(revno=80, version='2.0'),
        _build_revision(revno=156, version='git-0db35ea1'),
    ]
    store_mock.list_releases.return_value = (channel_map, channels, revisions)

    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('testcharm'),
    ]

    expected = [
        "Track    Channel    Version       Revision",
        "latest   stable     v7            7",
        "         candidate  v7            7",
        "         beta       2.0           80",
        "         edge       git-0db35ea1  156",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_status_empty(caplog, store_mock):
    """Empty response from the store."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    store_mock.list_releases.return_value = [], [], []
    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    expected = "Nothing found"
    assert [expected] == [rec.message for rec in caplog.records]


def test_status_name_guessing_ok(caplog, store_mock):
    """Get the status after guessing the charm's name correctly."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")
    store_mock.list_releases.return_value = [], [], []

    args = Namespace(name=None)
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = 'guessed-name'
        StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('guessed-name'),
    ]


def test_status_name_guessing_bad():
    """The charm name couldn't be guessed."""
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = None

        args = Namespace(name=None)
        with pytest.raises(CommandError) as cm:
            StatusCommand('group').run(args)

        assert str(cm.value) == (
            "Can't access name in 'metadata.yaml' file. The 'status' command needs to "
            "be executed in a valid project's directory, or indicate the charm name with "
            "the --name option.")


def test_status_channels_not_released_with_fallback(caplog, store_mock):
    """Support gaps in channel releases, having fallbacks."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    channel_map = [
        Release(revision=7, channel='latest/stable', expires_at=None),
        Release(revision=80, channel='latest/edge', expires_at=None),
    ]
    channels = _build_channels()
    revisions = [
        _build_revision(revno=7, version='v7'),
        _build_revision(revno=80, version='2.0'),
    ]
    store_mock.list_releases.return_value = (channel_map, channels, revisions)

    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('testcharm'),
    ]

    expected = [
        "Track    Channel    Version    Revision",
        "latest   stable     v7         7",
        "         candidate  ↑          ↑",
        "         beta       ↑          ↑",
        "         edge       2.0        80",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_status_channels_not_released_without_fallback(caplog, store_mock):
    """Support gaps in channel releases, nothing released in more stable ones."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    channel_map = [
        Release(revision=5, channel='latest/beta', expires_at=None),
        Release(revision=12, channel='latest/edge', expires_at=None),
    ]
    channels = _build_channels()
    revisions = [
        _build_revision(revno=5, version='5.1'),
        _build_revision(revno=12, version='almostready'),
    ]
    store_mock.list_releases.return_value = (channel_map, channels, revisions)

    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('testcharm'),
    ]

    expected = [
        "Track    Channel    Version      Revision",
        "latest   stable     -            -",
        "         candidate  -            -",
        "         beta       5.1          5",
        "         edge       almostready  12",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_status_multiple_tracks(caplog, store_mock):
    """Support multiple tracks."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    channel_map = [
        Release(revision=503, channel='latest/stable', expires_at=None),
        Release(revision=1, channel='2.0/edge', expires_at=None),
    ]
    channels_latest = _build_channels()
    channels_track = _build_channels(track='2.0')
    channels = channels_latest + channels_track
    revisions = [
        _build_revision(revno=503, version='7.5.3'),
        _build_revision(revno=1, version='1'),
    ]
    store_mock.list_releases.return_value = (channel_map, channels, revisions)

    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('testcharm'),
    ]

    expected = [
        "Track    Channel    Version    Revision",
        "latest   stable     7.5.3      503",
        "         candidate  ↑          ↑",
        "         beta       ↑          ↑",
        "         edge       ↑          ↑",
        "2.0      stable     -          -",
        "         candidate  -          -",
        "         beta       -          -",
        "         edge       1          1",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_status_tracks_order(caplog, store_mock):
    """Respect the track ordering from the store."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    channel_map = [
        Release(revision=1, channel='latest/edge', expires_at=None),
        Release(revision=2, channel='aaa/edge', expires_at=None),
        Release(revision=3, channel='2.0/edge', expires_at=None),
        Release(revision=4, channel='zzz/edge', expires_at=None),
    ]
    channels_latest = _build_channels()
    channels_track_1 = _build_channels(track='zzz')
    channels_track_2 = _build_channels(track='2.0')
    channels_track_3 = _build_channels(track='aaa')
    channels = channels_latest + channels_track_1 + channels_track_2 + channels_track_3
    revisions = [
        _build_revision(revno=1, version='v1'),
        _build_revision(revno=2, version='v2'),
        _build_revision(revno=3, version='v3'),
        _build_revision(revno=4, version='v4'),
    ]
    store_mock.list_releases.return_value = (channel_map, channels, revisions)

    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('testcharm'),
    ]

    expected = [
        "Track    Channel    Version    Revision",
        "latest   stable     -          -",
        "         candidate  -          -",
        "         beta       -          -",
        "         edge       v1         1",
        "zzz      stable     -          -",
        "         candidate  -          -",
        "         beta       -          -",
        "         edge       v4         4",
        "2.0      stable     -          -",
        "         candidate  -          -",
        "         beta       -          -",
        "         edge       v3         3",
        "aaa      stable     -          -",
        "         candidate  -          -",
        "         beta       -          -",
        "         edge       v2         2",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_status_with_one_branch(caplog, store_mock):
    """Support having one branch."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    tstamp_with_timezone = parser.parse('2020-07-03T20:30:40Z')
    channel_map = [
        Release(revision=5, channel='latest/beta', expires_at=None),
        Release(revision=12, channel='latest/beta/mybranch', expires_at=tstamp_with_timezone),
    ]
    channels = _build_channels()
    channels.append(
        Channel(
            name='latest/beta/mybranch', fallback='latest/beta',
            track='latest', risk='beta', branch='mybranch'))
    revisions = [
        _build_revision(revno=5, version='5.1'),
        _build_revision(revno=12, version='ver.12'),
    ]
    store_mock.list_releases.return_value = (channel_map, channels, revisions)

    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('testcharm'),
    ]

    expected = [
        "Track    Channel        Version    Revision    Expires at",
        "latest   stable         -          -",
        "         candidate      -          -",
        "         beta           5.1        5",
        "         edge           ↑          ↑",
        "         beta/mybranch  ver.12     12          2020-07-03T20:30:40+00:00",
    ]
    assert expected == [rec.message for rec in caplog.records]


def test_status_with_multiple_branches(caplog, store_mock):
    """Support having multiple branches."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")

    tstamp_with_timezone = parser.parse('2020-07-03T20:30:40Z')
    channel_map = [
        Release(revision=5, channel='latest/beta', expires_at=None),
        Release(revision=12, channel='latest/beta/branch-1', expires_at=tstamp_with_timezone),
        Release(revision=15, channel='latest/beta/branch-2', expires_at=tstamp_with_timezone),
    ]
    channels = _build_channels()
    channels.extend([
        Channel(
            name='latest/beta/branch-1', fallback='latest/beta',
            track='latest', risk='beta', branch='branch-1'),
        Channel(
            name='latest/beta/branch-2', fallback='latest/beta',
            track='latest', risk='beta', branch='branch-2'),
    ])
    revisions = [
        _build_revision(revno=5, version='5.1'),
        _build_revision(revno=12, version='ver.12'),
        _build_revision(revno=15, version='15.0.0'),
    ]
    store_mock.list_releases.return_value = (channel_map, channels, revisions)

    args = Namespace(name='testcharm')
    StatusCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.list_releases('testcharm'),
    ]

    expected = [
        "Track    Channel        Version    Revision    Expires at",
        "latest   stable         -          -",
        "         candidate      -          -",
        "         beta           5.1        5",
        "         edge           ↑          ↑",
        "         beta/branch-1  ver.12     12          2020-07-03T20:30:40+00:00",
        "         beta/branch-2  15.0.0     15          2020-07-03T20:30:40+00:00",
    ]
    assert expected == [rec.message for rec in caplog.records]


# -- tests for create library command

def test_createlib_simple(caplog, store_mock, tmp_path, monkeypatch):
    """Happy path with result from the Store."""
    caplog.set_level(logging.INFO, logger="charmcraft.commands")
    monkeypatch.chdir(tmp_path)

    lib_id = 'test-example-lib-id'
    store_mock.create_library_id.return_value = lib_id

    args = Namespace(lib_name='testlib')
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = 'testcharm'
        CreateLibCommand('group').run(args)

    assert store_mock.mock_calls == [
        call.create_library_id('testcharm', 'testlib'),
    ]
    expected = [
        "Library charms.testcharm.v0.testlib created with id test-example-lib-id.",
        "Make sure to add the library file to your project: lib/charms/testcharm/v0/testlib.py",
    ]
    assert expected == [rec.message for rec in caplog.records]
    created_lib_file = tmp_path / 'lib' / 'charms' / 'testcharm' / 'v0' / 'testlib.py'

    env = get_templates_environment('charmlibs')
    expected_newlib_content = env.get_template('new_library.py.j2').render(lib_id=lib_id)
    assert created_lib_file.read_text() == expected_newlib_content


def test_createlib_name_from_metadata_problem(store_mock):
    """The metadata wasn't there to get the name."""
    args = Namespace(lib_name='testlib')
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = None
        with pytest.raises(CommandError) as cm:
            CreateLibCommand('group').run(args)
        assert str(cm.value) == (
            "Can't access name in 'metadata.yaml' file. The 'create-lib' command needs to "
            "be executed in a valid project's directory.")


@pytest.mark.parametrize('lib_name', [
    'foo.bar',
    'foo/bar',
    'Foo',
    '123foo',
    '_foo',
])
def test_createlib_invalid_name(lib_name):
    """Verify that it can not be used with an invalid name."""
    args = Namespace(lib_name=lib_name)
    with pytest.raises(CommandError) as err:
        CreateLibCommand('group').run(args)
    assert str(err.value) == (
        "Invalid library name (can be only lowercase alphanumeric "
        "characters and underscore, starting with alpha).")


def test_createlib_path_already_there(tmp_path, monkeypatch):
    """The intended-to-be-created library is already there."""
    monkeypatch.chdir(tmp_path)

    factory.create_lib_filepath('test-charm-name', 'testlib', api=0)
    args = Namespace(lib_name='testlib')
    with patch('charmcraft.commands.store.get_name_from_metadata') as mock:
        mock.return_value = 'test-charm-name'
        with pytest.raises(CommandError) as err:
            CreateLibCommand('group').run(args)

    assert str(err.value) == (
        "The indicated library already exists on lib/charms/test-charm-name/v0/testlib.py")


# -- tests for _get_lib_info helper

def _create_lib(extra_content=None, metadata_id=None, metadata_api=None, metadata_patch=None):
    """Helper to create the structures on disk for a given lib.

    WARNING: this function has the capability of creating INCORRECT structures on disk.

    This is specific for the _get_lib_info tests below, other tests should use the
    functionality provided by the factory.
    """
    base_dir = pathlib.Path('lib')
    lib_file = base_dir / 'charms' / 'testcharm' / 'v3' / 'testlib.py'
    lib_file.parent.mkdir(parents=True, exist_ok=True)

    # save the content to that specific file under custom structure
    if metadata_id is None:
        metadata_id = "LIBID = 'test-lib-id'"
    if metadata_api is None:
        metadata_api = "LIBAPI = 3"
    if metadata_patch is None:
        metadata_patch = "LIBPATCH = 14"

    fields = [metadata_id, metadata_api, metadata_patch]
    with lib_file.open('wt', encoding='utf8') as fh:
        for f in fields:
            if f:
                fh.write(f + '\n')
        if extra_content:
            fh.write(extra_content)

    return lib_file


def test_getlibinfo_success_simple(tmp_path, monkeypatch):
    """Simple basic case of success getting info from the library."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib()

    lib_data = _get_lib_info(lib_path=test_path)
    assert lib_data.lib_id == 'test-lib-id'
    assert lib_data.api == 3
    assert lib_data.patch == 14
    assert lib_data.content_hash is not None
    assert lib_data.content is not None
    assert lib_data.full_name == 'charms.testcharm.v3.testlib'
    assert lib_data.path == test_path
    assert lib_data.lib_name == 'testlib'
    assert lib_data.charm_name == 'testcharm'


def test_getlibinfo_success_content(tmp_path, monkeypatch):
    """Check that content and its hash are ok."""
    monkeypatch.chdir(tmp_path)
    extra_content = """
        extra lines for the file
        extra non-ascii, for sanity: ñáéíóú
        the content is everything, this plus metadata
        the hash should be of this, excluding metadata
    """
    test_path = _create_lib(extra_content=extra_content)

    lib_data = _get_lib_info(lib_path=test_path)
    assert lib_data.content == test_path.read_text()
    assert lib_data.content_hash == hashlib.sha256(extra_content.encode('utf8')).hexdigest()


@pytest.mark.parametrize('name', [
    'charms.testcharm.v3.testlib.py',
    'charms.testcharm.testlib',
    'testcharm.v2.testlib',
    'mycharms.testcharm.v2.testlib',
])
def test_getlibinfo_bad_name(name):
    """Different combinations of a bad library name."""
    with pytest.raises(CommandError) as err:
        _get_lib_info(full_name=name)
    assert str(err.value) == (
        "Library full name {!r} must conform to the charms.<charm>.v<API>.<libname> structure."
        .format(name))


@pytest.mark.parametrize('path', [
    'charms/testcharm/v3/testlib',
    'charms/testcharm/v3/testlib.html',
    'charms/testcharm/v3/testlib.',
    'charms/testcharm/testlib.py',
    'testcharm/v2/testlib.py',
    'mycharms/testcharm/v2/testlib.py',
])
def test_getlibinfo_bad_path(path):
    """Different combinations of a bad library path."""
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=pathlib.Path(path))
    assert str(err.value) == (
        "Library path {} must conform to the lib/charms/<charm>/v<API>/<libname>.py structure."
        .format(path))


@pytest.mark.parametrize('name', [
    'charms.testcharm.v-three.testlib',
    'charms.testcharm.v-3.testlib',
    'charms.testcharm.3.testlib',
    'charms.testcharm.vX.testlib',
])
def test_getlibinfo_bad_api(name):
    """Different combinations of a bad api in the path/name."""
    with pytest.raises(CommandError) as err:
        _get_lib_info(full_name=name)
    assert str(err.value) == (
        "The API version in the library path must be 'vN' where N is an integer.")


def test_getlibinfo_missing_library_from_name():
    """Partial case for when the library is not found in disk, starting from the name."""
    test_name = 'charms.testcharm.v3.testlib'
    # no create lib!
    lib_data = _get_lib_info(full_name=test_name)
    assert lib_data.lib_id is None
    assert lib_data.api == 3
    assert lib_data.patch == -1
    assert lib_data.content_hash is None
    assert lib_data.content is None
    assert lib_data.full_name == test_name
    assert lib_data.path == pathlib.Path('lib') / 'charms' / 'testcharm' / 'v3' / 'testlib.py'
    assert lib_data.lib_name == 'testlib'
    assert lib_data.charm_name == 'testcharm'


def test_getlibinfo_missing_library_from_path():
    """Partial case for when the library is not found in disk, starting from the path."""
    test_path = pathlib.Path('lib') / 'charms' / 'testcharm' / 'v3' / 'testlib.py'
    # no create lib!
    lib_data = _get_lib_info(lib_path=test_path)
    assert lib_data.lib_id is None
    assert lib_data.api == 3
    assert lib_data.patch == -1
    assert lib_data.content_hash is None
    assert lib_data.content is None
    assert lib_data.full_name == 'charms.testcharm.v3.testlib'
    assert lib_data.path == test_path
    assert lib_data.lib_name == 'testlib'
    assert lib_data.charm_name == 'testcharm'


def test_getlibinfo_malformed_metadata_field(tmp_path, monkeypatch):
    """Some metadata field is not really valid."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_id="LIBID = foo = 23")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == r"Bad metadata line in {}: b'LIBID = foo = 23\n'".format(test_path)


def test_getlibinfo_missing_metadata_field(tmp_path, monkeypatch):
    """Some metadata field is not present."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_patch="", metadata_api="")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} is missing the mandatory metadata fields: LIBAPI, LIBPATCH.".format(test_path))


def test_getlibinfo_api_not_int(tmp_path, monkeypatch):
    """The API is not an integer."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_api="LIBAPI = v3")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBAPI is not zero or a positive integer.".format(test_path))


def test_getlibinfo_api_negative(tmp_path, monkeypatch):
    """The API is not negative."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_api="LIBAPI = -3")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBAPI is not zero or a positive integer.".format(test_path))


def test_getlibinfo_patch_not_int(tmp_path, monkeypatch):
    """The PATCH is not an integer."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_patch="LIBPATCH = beta3")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBPATCH is not zero or a positive integer.".format(test_path))


def test_getlibinfo_patch_negative(tmp_path, monkeypatch):
    """The PATCH is not negative."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_patch="LIBPATCH = -1")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBPATCH is not zero or a positive integer.".format(test_path))


def test_getlibinfo_api_patch_both_zero(tmp_path, monkeypatch):
    """Invalid combination of both API and PATCH being 0."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_patch="LIBPATCH = 0", metadata_api="LIBAPI = 0")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata fields LIBAPI and LIBPATCH cannot both be zero.".format(test_path))


def test_getlibinfo_metadata_api_different_path_api(tmp_path, monkeypatch):
    """The API value included in the file is different than the one in the path."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_api="LIBAPI = 99")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBAPI is different from the version in the path."
        .format(test_path))


def test_getlibinfo_libid_non_string(tmp_path, monkeypatch):
    """The ID is not really a string."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_id="LIBID = 99")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBID must be a non-empty ASCII string.".format(test_path))


def test_getlibinfo_libid_non_ascii(tmp_path, monkeypatch):
    """The ID is not ASCII."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_id="LIBID = 'moño'")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBID must be a non-empty ASCII string.".format(test_path))


def test_getlibinfo_libid_empty(tmp_path, monkeypatch):
    """The ID is empty."""
    monkeypatch.chdir(tmp_path)
    test_path = _create_lib(metadata_id="LIBID = ''")
    with pytest.raises(CommandError) as err:
        _get_lib_info(lib_path=test_path)
    assert str(err.value) == (
        "Library {} metadata field LIBID must be a non-empty ASCII string.".format(test_path))
