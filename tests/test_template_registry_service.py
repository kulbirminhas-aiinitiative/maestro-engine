import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import pytest
from bson import ObjectId
from fastapi.testclient import TestClient

import services.template_registry_service.app as svc_module
from services.template_registry_service.app import app


class DummyCollection:
    def __init__(self):
        # internal store maps ObjectId -> document dict (with _id as ObjectId)
        self.store = {}

    async def find_one(self, query):
        # support query by name or _id
        if not query:
            return None
        if "name" in query:
            for doc in self.store.values():
                if doc.get("name") == query["name"]:
                    return self._as_return(doc)
        if "_id" in query:
            qid = query["_id"]
            # qid may be ObjectId or string
            try:
                if isinstance(qid, str):
                    qid = ObjectId(qid)
            except Exception:
                pass
            doc = self.store.get(qid)
            if doc:
                return self._as_return(doc)
        return None

    async def insert_one(self, document):
        # ensure _id present
        doc = dict(document)
        oid = doc.get("_id")
        if isinstance(oid, str):
            oid = ObjectId(oid)
        if oid is None:
            oid = ObjectId()
        doc["_id"] = oid
        # store copy
        self.store[oid] = doc

        class _Res:
            def __init__(self, inserted_id):
                self.inserted_id = inserted_id

        return _Res(inserted_id=oid)

    def find(self, query):
        # return an async-compatible object with to_list
        async def _to_list(limit):
            results = []
            for doc in self.store.values():
                match = True
                if query:
                    if "technology_stack" in query:
                        # query like {"technology_stack":{"$in": [val]}}
                        val = query["technology_stack"]["$in"][0]
                        if val not in doc.get("technology_stack", []):
                            match = False
                    if "tags" in query:
                        val = query["tags"]["$in"][0]
                        if val not in doc.get("tags", []):
                            match = False
                if match:
                    results.append(self._as_return(doc))
            return results

        class _Cursor:
            def __init__(self, to_list_fn):
                self._to_list = to_list_fn

            async def to_list(self, limit):
                return await self._to_list(limit)

        return _Cursor(_to_list)

    async def update_one(self, filter_query, update):
        # only support $set
        qid = filter_query.get("_id")
        try:
            if isinstance(qid, str):
                qid = ObjectId(qid)
        except Exception:
            pass
        doc = self.store.get(qid)

        class _Res:
            def __init__(self, modified_count):
                self.modified_count = modified_count

        if not doc:
            return _Res(modified_count=0)
        if "$set" in update:
            for k, v in update["$set"].items():
                doc[k] = v
            self.store[qid] = doc
            return _Res(modified_count=1)
        return _Res(modified_count=0)

    async def delete_one(self, filter_query):
        qid = filter_query.get("_id")
        try:
            if isinstance(qid, str):
                qid = ObjectId(qid)
        except Exception:
            pass
        if qid in self.store:
            self.store.pop(qid)

            class _Res:
                def __init__(self, deleted_count):
                    self.deleted_count = deleted_count

            return _Res(deleted_count=1)

        class _Res0:
            def __init__(self, deleted_count):
                self.deleted_count = deleted_count

        return _Res0(deleted_count=0)

    def _as_return(self, doc):
        # return a shallow copy with _id converted to str for JSON serialization
        copy = dict(doc)
        copy["_id"] = str(copy["_id"]) if isinstance(copy.get("_id"), ObjectId) else copy.get("_id")
        return copy


class DummyDB:
    def __init__(self):
        self._templates = DummyCollection()

    def __getitem__(self, name):
        if name == "templates":
            return self._templates
        raise KeyError(name)


@pytest.fixture(autouse=True)
def monkeypatch_db(monkeypatch):
    dummy = DummyDB()
    # replace the db used by the service module
    monkeypatch.setattr(svc_module, "db", dummy)
    return dummy


client = TestClient(app)


def test_openapi_docs_available():
    r = client.get("/docs")
    assert r.status_code == 200


def test_create_and_crud_template(monkeypatch_db):
    payload = {
        "name": "test-template",
        "description": "A test template",
        "technology_stack": ["Python", "FastAPI"],
        "repo_url": "https://example.com/repo.git",
        "version": "0.1.0",
        "tags": ["test", "example"],
    }

    # Create
    res = client.post("/templates/", json=payload)
    assert res.status_code == 201
    body = res.json()
    assert body["name"] == payload["name"]
    tid = body["_id"]

    # Create duplicate (same name) should return 409
    res2 = client.post("/templates/", json=payload)
    assert res2.status_code == 409

    # List
    res_list = client.get("/templates/")
    assert res_list.status_code == 200
    list_body = res_list.json()
    assert any(t["name"] == payload["name"] for t in list_body)

    # Get by id
    res_get = client.get(f"/templates/{tid}")
    assert res_get.status_code == 200
    assert res_get.json()["name"] == payload["name"]

    # Update
    update_payload = {"description": "An updated description"}
    res_upd = client.put(f"/templates/{tid}", json=update_payload)
    assert res_upd.status_code == 200
    assert res_upd.json()["description"] == update_payload["description"]

    # Delete
    res_del = client.delete(f"/templates/{tid}")
    assert res_del.status_code == 204

    # Get after delete -> 404
    res_not = client.get(f"/templates/{tid}")
    assert res_not.status_code == 404
