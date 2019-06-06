import json

from mongocontents.ipycompat import Unicode
from mongocontents.genericmanager import from_dict, GenericContentsManager

class MongoContentsManager(GenericContentsManager):

    def __init__(self, *args, **kwargs):
        super(MongoContentsManager, self).__init__(*args, **kwargs)

