import abc
import json
import urllib.parse
import uuid
import hashlib
import datetime
import logging
from bspump.asab.web.rest.json import JSONDumper
import http.client
import typing

#

L = logging.getLogger(__name__)

#


class UpsertorABC(abc.ABC):
    def __init__(self, storage, collection, obj_id, version=None):
        self.Storage = storage
        self.Collection = collection
        self.ObjId = obj_id

        self.Version = version

        now = datetime.datetime.now(datetime.timezone.utc)
        self.ModSet = {
            "_m": now,  # Set the modification datetime
        }
        if version == 0:
            self.ModSet["_c"] = now  # Set the creation datetime

        self.ModUnset = {}

        self.ModInc = {
            "_v": 1,  # Increment '_v' at every change
        }

        self.ModPush = {}
        self.ModPull = {}

        self.WebhookResponseData = {}

    def get_id_name(self):
        return "_id"

    @classmethod
    def generate_id(cls) -> bytes:
        """
        Generate a unique ID string using a combination of a random UUID and a SHA-256 hash.

        Returns:
                A string representation of the generated ID.
        """
        m = hashlib.sha256()
        m.update(uuid.uuid4().bytes)
        return m.digest()

    def set(self, objField, value, encrypt=False, encrypt_iv=None):
        """
        Add key and value to the upsertor.

        Args:
                objField: Key of the object.
                value: Value of the object.
                encrypt: Allow encryption.
                encrypt_iv: Custom initialization vector.
        """

        if encrypt:
            value = self.Storage.aes_encrypt(value, iv=encrypt_iv)
        self.ModSet[objField] = value

    def unset(self, obj_field):
        """
        Scalar unset
        """
        self.ModUnset[obj_field] = ""

    def increment(self, field_name, amount=1):
        """
        Scalar increment
        """
        self.ModInc[field_name] = amount

    def decrement(self, field_name, amount=1):
        """
        Scalar decrement
        """
        return self.increment(field_name, -amount)

    def push(self, field_name, value):
        """
        Push an item into a list
        """
        if self.ModPush.get(field_name) is None:
            self.ModPush[field_name] = []
        self.ModPush[field_name].append(value)

    def pull(self, field_name, value):
        """
        Pull an item from a list
        """
        if self.ModPull.get(field_name) is None:
            self.ModPull[field_name] = []
        self.ModPull[field_name].append(value)

    @abc.abstractmethod
    async def execute(
        self,
        custom_data: typing.Optional[dict] = None,
        event_type: typing.Optional[str] = None,
    ):
        """
        Commit upsertor data to the storage. Afterwards, send a webhook request with upsertion details.

        Args:
                custom_data: Custom execution data. Included in webhook payload.
                event_type: Event type included in webhook payload.

        Raises:
                DuplicateError: Raised if there is a colliding object already stored in a storage.
        """

        pass

    async def webhook(self, data: dict):
        # TODO: add docstring
        assert self.Storage.WebhookURIs is not None
        json_dump = JSONDumper(pretty=False)(data)
        for uri in self.Storage.WebhookURIs:
            self.WebhookResponseData[uri] = await self.Storage.ProactorService.execute(
                self._webhook, json_dump, uri, self.Storage.WebhookAuth
            )

    def _webhook(self, data, uri, auth=None):
        u = urllib.parse.urlparse(uri)
        if u.scheme == "https":
            conn = http.client.HTTPSConnection(u.netloc)
        else:
            conn = http.client.HTTPConnection(u.netloc)

        headers = {"Content-Type": "application/json"}
        if auth is not None:
            headers["Authorization"] = auth

        try:
            conn.request("PUT", uri, data, headers)
            response = conn.getresponse()
            if response.status // 100 != 2:
                text = response.read()
                L.error(
                    "Webhook endpoint responded with {}: {}".format(
                        response.status, text
                    ),
                    struct_data={"uri": uri},
                )
                return
            self.WebhookResponseData = json.load(response)
        except ConnectionRefusedError:
            L.error(
                "Webhook call failed: Connection refused.", struct_data={"uri": uri}
            )
            return
        except json.decoder.JSONDecodeError as e:
            L.error(
                "Failed to decode JSON response from webhook: {}".format(str(e)),
                struct_data={"uri": uri},
            )
        except Exception as e:
            L.error(
                "Webhook call failed with {}: {}".format(type(e).__name__, str(e)),
                struct_data={"uri": uri},
            )
        finally:
            conn.close()
