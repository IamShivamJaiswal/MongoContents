import os
import json
import mimetypes
import datetime
import itertools
import pymongo

from tornado.web import HTTPError
from nbformat.v4 import new_notebook
from notebook.transutils import _

from mongocontents.genericfs import GenericFSError, NoSuchFile,MongoFS
from mongocontents.ipycompat import ContentsManager
from mongocontents.ipycompat import HasTraits, Unicode ,List
from mongocontents.ipycompat import reads, from_dict, GenericFileCheckpoints



DUMMY_CREATED_DATE = datetime.datetime.fromtimestamp(86400)
NBFORMAT_VERSION = 4


class GenericContentsManager(ContentsManager, HasTraits):

    # This makes the checkpoints get saved on this directory
    root_dir = Unicode("./", config=True)

    hide_globs = List(Unicode(), [
            u'__pycache__', '*.pyc', '*.pyo',
            '.DS_Store', '*.so', '*.dylib', '*~',
        ], config=True, help="""
        Glob patterns to hide in file and directory listings.
    """)
    untitled_notebook = Unicode(_("Untitled"), config=True,
        help="The base name used when creating untitled notebooks."
    )

    untitled_file = Unicode("untitled", config=True,
        help="The base name used when creating untitled files."
    )

    untitled_directory = Unicode("Untitled Folder", config=True,
        help="The base name used when creating untitled directories."
    )

    def __init__(self, *args, **kwargs):
        super(GenericContentsManager, self).__init__(*args, **kwargs)

    fs = MongoFS() 

    def _checkpoints_class_default(self):
        return GenericFileCheckpoints

    def do_error(self, msg, code=500):
        raise HTTPError(code, msg)

    def no_such_entity(self, path):
        self.do_error("No such entity: [{path}]".format(path=path), 404)

    def already_exists(self, path):
        thing = "File" if self.file_exists(path) else "Directory"
        self.do_error(u"{thing} already exists: [{path}]".format(thing=thing, path=path), 409)

    def guess_type(self, path, allow_directory=True):
        """
        Guess the type of a file.
        If allow_directory is False, don't consider the possibility that the
        file is a directory.
        Parameters
        ----------
            obj: s3.Object or string
        """
        if path.endswith(".ipynb"):
            return "notebook"
        elif allow_directory and self.dir_exists(path):
            return "directory"
        else:
            return "file"

    def file_exists(self, path):
        # Does a file exist at the given path?
        self.log.debug("MongoContents.GenericManager.file_exists: ('%s')", path)
        return self.fs.isfile(path)

    def dir_exists(self, path):
        # Does a directory exist at the given path?
        self.log.debug("MongoContents.GenericManager.dir_exists: path('%s')", path)
        return self.fs.isdir(path) or self.fs.isdir(path.strip("/"))

    def get(self, path, content=True, type=None, format=None):
        # Get a file or directory model.  
        self.log.debug("MongoContents.GenericManager.get] path('%s') type(%s) format(%s)", path, type, format)
        path = path.strip('/')
        print("get called") 

        if type is None:
            type = self.guess_type(path)
        print(type)
        try:
            func = {
                "directory": self._get_directory,
                "notebook": self._get_notebook,
                "file": self._get_file,
            }[type]
        except KeyError:
            raise ValueError("Unknown type passed: '{}'".format(type))

        return func(path=path, content=content, format=format)

    def _get_directory(self, path, content=True, format=None):
        self.log.debug("MongoContents.GenericManager.get_directory: path('%s') content(%s) format(%s)", path, content, format)
        print("MongoContents.GenericManager.get_directory: path('%s') content(%s) format(%s)", path, content, format)
        return self._directory_model_from_path(path, content=content)

    def _get_notebook(self, path, content=True, format=None):
        self.log.debug("MongoContents.GenericManager.get_notebook: path('%s') type(%s) format(%s)", path, content, format)
        return self._notebook_model_from_path(path, content=content, format=format)

    def _get_file(self, path, content=True, format=None):
        self.log.debug("MongoContents.GenericManager.get_file: path('%s') type(%s) format(%s)", path, content, format)
        return self._file_model_from_path(path, content=content, format=format)

    def _directory_model_from_path(self, path, content=False):
        print("directory model called",path)
        self.log.debug("MongoContents.GenericManager._directory_model_from_path: path('%s') type(%s)", path, content)
        model = base_directory_model(path)
        if content:
            if not self.dir_exists(path):
                self.no_such_entity(path)
            model["format"] = "json"
            dir_content = self.fs.ls(path=path)
            model["content"] = self._convert_file_records(dir_content)
        print(model)
        return model

    def _notebook_model_from_path(self, path, content=False, format=None):
        """
        Build a notebook model from database record.
        """
        model = base_model(path)
        model["type"] = "notebook"
        # if self.fs.isfile(path):
        #     model["last_modified"] = model["created"] = self.fs.lstat(path)["ST_MTIME"]
        # else:
        #     model["last_modified"] = model["created"] = DUMMY_CREATED_DATE
        model["last_modified"] = model["created"] = DUMMY_CREATED_DATE

        if content:
            if not self.fs.isfile(path):
                self.no_such_entity(path)
            file_content = self.fs.read(path)
            
            nb_content = reads(file_content, as_version=NBFORMAT_VERSION)
            self.mark_trusted_cells(nb_content, path)
            model["format"] = "json"
            model["content"] = nb_content
            self.validate_notebook_model(model)
        return model

    def _file_model_from_path(self, path, content=False, format=None):
        """
        Build a file model from database record.
        """
        model = base_model(path)
        model["type"] = "file"
        if self.fs.isfile(path):
            model["last_modified"] = model["created"] = self.fs.lstat(path)["ST_MTIME"]
        else:
            model["last_modified"] = model["created"] = DUMMY_CREATED_DATE
        if content:
            try:
                content = self.fs.read(path)
            except NoSuchFile as e:
                self.no_such_entity(e.path)
            except GenericFSError as e:
                self.do_error(str(e), 500)
            model["format"] = format or "text"
            model["content"] = content
            model["mimetype"] = mimetypes.guess_type(path)[0] or "text/plain"
            if format == "base64":
                model["format"] = format or "base64"
                from base64 import b64decode
                model["content"] = b64decode(content)
        return model

    def _convert_file_records(self, paths):
        """
        Applies _notebook_model_from_s3_path or _file_model_from_s3_path to each entry of `paths`,
        depending on the result of `guess_type`.
        """
        ret = []
        print(paths)
        for path in paths:
            # path = self.fs.remove_prefix(path, self.prefix)  # Remove bucket prefix from paths
            # if os.path.basename(path) == self.fs.dir_keep_file:
            #     continue
            type_ = self.guess_type(path, allow_directory=True)
            if type_ == "notebook":
                ret.append(self._notebook_model_from_path(path, False))
            elif type_ == "file":
                ret.append(self._file_model_from_path(path, False, None))
            elif type_ == "directory":
                ret.append(self._directory_model_from_path(path, False))
            else:
                self.do_error("Unknown file type %s for file '%s'" % (type_, path), 500)
        return ret

    def save(self, model, path):
        print("Save called")
        """Save a file or directory model to path.
        """
        self.log.debug("MongoContents.GenericManager: save %s: '%s'", model, path)
        if "type" not in model:
            self.do_error("No model type provided", 400)
        if "content" not in model and model["type"] != "directory":
            self.do_error("No file content provided", 400)

        if model["type"] not in ("file", "directory", "notebook"):
            self.do_error("Unhandled contents type: %s" % model["type"], 400)

        try:
            if model["type"] == "notebook":
                validation_message = self._save_notebook(model, path)
            elif model["type"] == "file":
                validation_message = self._save_file(model, path)
            else:
                validation_message = self._save_directory(path)
        except Exception as e:
            self.log.error("Error while saving file: %s %s", path, e, exc_info=True)
            self.do_error("Unexpected error while saving file: %s %s" % (path, e), 500)

        model = self.get(path, type=model["type"], content=False)
        if validation_message is not None:
            model["message"] = validation_message
        return model

    def new_untitled(self, path='', type='', ext=''):
        """Create a new untitled file or directory in path
        
        path must be a directory
        
        File extension can be specified.
        
        Use `new` to create files with a fully specified path (including filename).
        """
        #path = path.strip('/')
        print(path)
        if not self.dir_exists(path):
            raise HTTPError(404, 'No such directory: here %s' % path)
        
        model = {}
        if type:
            model['type'] = type
        
        if ext == '.ipynb':
            model.setdefault('type', 'notebook')
        else:
            model.setdefault('type', 'file')
        
        insert = ''
        if model['type'] == 'directory':
            untitled = self.untitled_directory
            insert = ' '
        elif model['type'] == 'notebook':
            untitled = self.untitled_notebook
            ext = '.ipynb'
        elif model['type'] == 'file':
            untitled = self.untitled_file
        else:
            raise HTTPError(400, "Unexpected model type: %r" % model['type'])
        
        name = self.increment_filename(untitled + ext, path, insert=insert)
        path = u'{0}/{1}'.format(path, name)
        return self.new(model, path)
    
    def new(self, model=None, path=''):
        """Create a new file or directory and return its model with no content.
        
        To create a new untitled entity in a directory, use `new_untitled`.
        """
        path = path.strip('/')
        if model is None:
            model = {}
        
        if path.endswith('.ipynb'):
            model.setdefault('type', 'notebook')
        else:
            model.setdefault('type', 'file')
        
        # no content, not a directory, so fill out new-file model
        if 'content' not in model and model['type'] != 'directory':
            if model['type'] == 'notebook':
                model['content'] = new_notebook()
                model['format'] = 'json'
            else:
                model['content'] = ''
                model['type'] = 'file'
                model['format'] = 'text'
        
        model = self.save(model, path)
        return model

    def increment_filename(self, filename, path='', insert=''):
        """Increment a filename until it is unique.

        Parameters
        ----------
        filename : unicode
            The name of a file, including extension
        path : unicode
            The API path of the target's directory
        insert: unicode
            The characters to insert after the base filename

        Returns
        -------
        name : unicode
            A filename that is unique, based on the input filename.
        """
        # Extract the full suffix from the filename (e.g. .tar.gz)
        path = path.strip('/')
        basename, dot, ext = filename.partition('.')
        suffix = dot + ext

        for i in itertools.count():
            if i:
                insert_i = '{}{}'.format(insert, i)
            else:
                insert_i = ''
            name = u'{basename}{insert}{suffix}'.format(basename=basename,
                insert=insert_i, suffix=suffix)
            if not self.exists(u'{}/{}'.format(path, name)):
                break
        return name
       
    def _save_notebook(self, model, path):
        print("Save Notebook ")
        nb_contents = from_dict(model['content'])
        self.check_and_sign(nb_contents, path)
        file_contents = model["content"]
        self.fs.write(path, file_contents)
        self.validate_notebook_model(model)
        return model.get("message")


    # def update(self, model, path):
    #     """Update the file's path

    #     For use in PATCH requests, to enable renaming a file without
    #     re-uploading its contents. Only used for renaming at the moment.
    #     """
    #     print("update call")
    #     return model
    # def _save_notebook(self, model, path):
    #     nb_contents = from_dict(model['content'])
    #     self.check_and_sign(nb_contents, path)
    #     file_contents = json.dumps(model["content"])
    #     self.fs.write(path, file_contents)
    #     self.validate_notebook_model(model)
    #     return model.get("message")

    def _save_file(self, model, path):
        file_contents = model["content"]
        file_format = model.get('format')
        self.fs.write(path, file_contents, file_format)

    def _save_directory(self, path):
        self.fs.mkdir(path)

    ############## Working################3
    def rename_file(self, old_path, new_path):
        """Rename a file or directory.
        NOTE: This method is unfortunately named on the base class.  It
        actually moves a file or a directory.
        """
        self.log.debug("MongoContents.GenericManager: Init rename of '%s' to '%s'", old_path, new_path)
        if self.file_exists(new_path) or self.dir_exists(new_path):
            self.already_exists(new_path)
        elif self.file_exists(old_path) or self.dir_exists(old_path):
            self.log.debug("MongoContents.GenericManager: Actually renaming '%s' to '%s'", old_path,
                           new_path)
            self.fs.mv(old_path, new_path)
        else:
            self.no_such_entity(old_path)

    def delete_file(self, path):
        """Delete the file or directory at path.
        """
        self.log.debug("MongoContents.GenericManager: delete_file '%s'", path)
        if self.file_exists(path):
            self.fs.rm(path,type="file")
        elif self.dir_exists(path):
            self.fs.rm(path,type="dir")
        else:
            self.no_such_entity(path)

    def is_hidden(self, path):
        """Is path a hidden directory or file?
        """
        self.log.debug("MongoContents.GenericManager: is_hidden '%s'", path)
        return False


def base_model(path):
    return {
        "name": path.rsplit('/', 1)[-1],
        "path": path,
        "writable": True,
        "last_modified": None,
        "created": None,
        "content": None,
        "format": None,
        "mimetype": None,
    }


def base_directory_model(path):
    model = base_model(path)
    model.update(
        type="directory",
        last_modified=DUMMY_CREATED_DATE,
        created=DUMMY_CREATED_DATE,)
    return model