"""
Generic FileSystem class to be used by the Content Manager
"""

from mongocontents.ipycompat import HasTraits
import pymongo
import json

class GenericFS(HasTraits):

    def ls(self, path=""):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def isfile(self, path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def isdir(self, path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def mv(self, old_path, new_path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def cp(self, old_path, new_path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def rm(self, path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def mkdir(self, path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def read(self, path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def lstat(self, path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def write(self, path, content, format):
        raise NotImplemented("Should be implemented by the file system abstraction")


class MongoFS():

    def __init__(self):
        client = pymongo.MongoClient("mongodb+srv://<username>:<password>@cluster0-p2bjs.mongodb.net/test?retryWrites=true&w=majority")
        self._db = client.jupyter
        
    def ls(self, path=""):
        collect = self._db.directory
        res = collect.find_one({'path':path},{ "_id": 0})
        if not res:
            return []
        else:
            return res["contains"]        
        
    def isfile(self, path):
        collect = self._db.files
        res = collect.find_one({'file':path},{ "_id": 0})
        #print(res)
        return True if res else False

    def isdir(self, path):
        collect = self._db.directory
        res = collect.find_one({'path':path},{ "_id": 0})
        return True if res else False

    def mv(self, old_path, new_path):
        collect = self._db.files
        collect.update_one({'file':old_path},{ "$set":{'file':new_path}})
        #folder logic should also need to be implemented
        collect = self._db.directory
        res = collect.find_one({'contains':{'$all':[old_path]}})
        for index,item in enumerate(res['contains']):
            if item == old_path:
                res['contains'][index] = new_path
        collect.update_one({'path':res['path']},{ "$set":{'contains':res['contains']}})
        


    def cp(self, old_path, new_path):
        raise NotImplemented("Should be implemented by the file system abstraction")

    def rm(self, path ,type=None):
        if type == "file":
            collect = self._db.files
            collect.delete_one({'path':path})
            collect = self._db.directory
            paths = path.split("/")
            if(len(paths)==1):
                old_path = ""
            else:
                old_path = "/"+"/".join(paths[:-1])
            res = collect.find_one({'path':{'$all':[old_path]}})
            res['contains'].remove(path)
            print(res['contains'])
            collect.update_one({'path':res['path']},{ "$set":{'contains':res['contains']}})
        else:
            collect = self._db.directory
            collect.delete_one({'path':path})
        # logic for deleting other files and folder should also be implement here


    def mkdir(self, path):
        collect = self._db.directory
        collect.insert_one({'path':path,'contains':[]})

    def read(self, path):
        collect = self._db.files
        res = collect.find_one({'file':path},{ "_id": 0})
        if not res:
            return []
        else:
            return res["content"]

    def lstat(self, path):
        collect = self._db.directory
        #raise NotImplemented("Should be implemented by the file system abstraction")

    def write(self, path, content):
        collect = self._db.files
        content = json.dumps(content)
        print(path)
        if collect.find_one({'file':path}):
            print("hereee")
            res = collect.update_one({'file':path},{ "$set":{'content':content}})
        else:
            print(path)
            collect.insert_one({'file':path,'content':content})
            collect = self._db.directory
            paths = path.split("/")
            if(len(paths)==1):
                old_path = ""
            else:
                old_path = "/"+"/".join(paths[:-1])
            print(old_path)
            res = collect.find_one({'path':{'$all':[old_path]}})
            res['contains'].append(path)
            print(res['contains'])
            collect.update_one({'path':res['path']},{ "$set":{'contains':res['contains']}})
        


class GenericFSError(Exception):
    pass


class NoSuchFile(GenericFSError):

    def __init__(self, path, *args, **kwargs):
        self.path = path
        self.message = "No such file or directory: {}".format(path)
        super(NoSuchFile, self).__init__(self.message, *args, **kwargs)