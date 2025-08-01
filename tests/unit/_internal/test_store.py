from __future__ import annotations

import os
import time
import typing as t
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import attr
import pytest

from bentoml import Tag
from bentoml._internal.store import Store
from bentoml._internal.store import StoreItem
from bentoml.exceptions import BentoMLException
from bentoml.exceptions import NotFound

if TYPE_CHECKING:
    from bentoml._internal.types import PathType


@attr.define(repr=False)
class DummyItem(StoreItem):
    _tag: Tag
    _path: Path
    _creation_time: datetime
    store: "DummyStore" = attr.field(init=False)

    @staticmethod
    def _export_ext() -> str:
        return "bentodummy"

    @property
    def tag(self) -> Tag:
        return self._tag

    @property
    def creation_time(self) -> datetime:
        return self._creation_time

    @staticmethod
    def create(tag: t.Union[str, Tag], creation_time: t.Optional[datetime] = None):
        creation_time = datetime.now() if creation_time is None else creation_time
        with DummyItem.store.register(tag) as path:
            Path(path, "tag").write_text(str(tag))
            Path(path, "ctime").write_text(creation_time.isoformat())

    @classmethod
    def from_path(cls, path: PathType) -> "DummyItem":
        path = Path(path)
        return DummyItem(
            Tag.from_str(path.joinpath("tag").read_text().strip()),
            path,
            datetime.fromisoformat(path.joinpath("ctime").read_text().strip()),
        )


class DummyStore(Store[DummyItem]):
    _item_type = DummyItem


def test_store(tmpdir: "Path"):
    store = DummyStore(tmpdir)

    open(os.path.join(tmpdir, ".DS_store"), "a", encoding="utf-8")

    DummyItem.store = store
    oldtime = datetime.now()
    DummyItem.create("test:version1")
    time.sleep(1)
    DummyItem.create("test:otherprefix")
    time.sleep(1)
    DummyItem.create(Tag("test", "version2"))
    time.sleep(1)
    DummyItem.create("test:version3", creation_time=oldtime)
    time.sleep(1)
    DummyItem.create("test1:version1")
    with pytest.raises(BentoMLException):
        DummyItem.create("test:version2")

    item = store.get("test:version1")
    assert item.tag == Tag("test", "version1")
    item = store.get("test:oth")
    assert item.tag == Tag("test", "otherprefix")
    latest = store.get("test:latest")
    assert latest.tag == Tag("test", "version2")
    latest = store.get("test")
    assert latest.tag == Tag("test", "version2")

    with pytest.raises(BentoMLException):
        store.get("test:ver")

    with pytest.raises(NotFound):
        store.get("nonexistent:latest")
    with pytest.raises(NotFound):
        store.get("test:version4")

    vers = store.list()
    assert set([ver.tag for ver in vers]) == {
        Tag("test", "version1"),
        Tag("test", "version2"),
        Tag("test", "version3"),
        Tag("test", "otherprefix"),
        Tag("test1", "version1"),
    }

    vers = store.list("test")
    assert set([ver.tag for ver in vers]) == {
        Tag("test", "version1"),
        Tag("test", "version2"),
        Tag("test", "version3"),
        Tag("test", "otherprefix"),
    }

    vers = store.list("test:version1")
    assert set([ver.tag for ver in vers]) == {Tag("test", "version1")}

    assert store.list("nonexistent:latest") == []
    assert store.list("test:version4") == []

    store.delete("test:version2")
    latest = store.get("test")
    assert latest.tag == Tag("test", "otherprefix")

    with pytest.raises(NotFound):
        store.delete("test:version4")

    store.delete("test1:version1")

    with pytest.raises(NotFound):
        store.get("test1")

    with pytest.raises(NotFound):
        store.list("test1")

    store.delete("test")

    with pytest.raises(NotFound):
        store.list("test")

    assert store.list() == []
