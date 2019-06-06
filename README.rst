MongoContents
===============

MongoContents is a MongoDB-backed implementation of `IPEP 27 <https://github.com/ipython/ipython/wiki/IPEP-27:-Contents-Service>`_.  It aims to a be a transparent, drop-in replacement for IPython's standard filesystem-backed storage system.  MongoContents' `MongoContentsManager` class can be used to replace all local filesystem storage with database-backed storage.These features are useful when running IPython in environments where you either don't have access to—or don't trust the reliability of—the local filesystem of your notebook server.
