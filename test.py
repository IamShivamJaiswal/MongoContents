import pymongo


class MongoFS():

    def __init__(self):
        client = pymongo.MongoClient("mongodb+srv://admin:admin@cluster0-p2bjs.mongodb.net/test?retryWrites=true&w=majority")
        self._db = client.jupyter
        print(self.ls(path="./"))

    def ls(self, path=""):
        collect = self._db.directory
        res = collect.find_one({'path':path},{ "_id": 0})
        return res['contains']
        #raise NotImplemented("Should be implemented by the file system abstraction")

    def isfile(self, path):
        collect = self._db.files
        res = collect.find_one({'file':path},{ "_id": 0})
        return True if res else False

    def isdir(self, path):
        collect = self._db.directory
        res = collect.find_one({'path':path},{ "_id": 0})
        return True if res else False

    def mv(self, old_path, new_path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def cp(self, old_path, new_path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def rm(self, path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def mkdir(self, path):
        collect = self._db.directory
        collect.insert_one({'path':path,'contains':[]})

    def read(self, path):
        collect = self._db.files
        res = collect.find_one({'file':path},{ "_id": 0})
        return res["content"]

    def lstat(self, path):
        collect = self._db.directory
        raise NotImplemented("Should be implemented by the file system abstraction")

    def write(self, path, content, format):
        collect = self._db.files
        res = collect.insert_one({'file':path,'content':content})


MongoFS()
