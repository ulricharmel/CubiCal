import cPickle
import numpy as np
from cubical.tools import logger, ModColor
log = logger.getLogger("flagging")


class SimpleParameterDB(object):
    """
    This class implements a simple parameter database
    """
    @staticmethod
    def create(filename, metadata=None):
        db = SimpleParameterDB()
        db._create(filename, metadata)
        return db

    @staticmethod
    def load(filename):
        db = SimpleParameterDB()
        db._load(filename)
        return db


    def _create(self, filename, metadata=None):
        """
        Creates a parameter database given by the filename, opens it in "create" mode
        
        Args:
            filename: name of database
            metadata: optional metadata to be stored in DB
        """
        self.mode = "create"
        self.filename = filename
        self._fobj = open(filename, 'w')
        self._parmdescs = {}

    def define_param(self, name, shape, dtype, axis_labels, grids, empty=0, metadata=None):
        """
        Defines a parameter. Only valid in "create" mode.
        
        Args:
            name:           name, e.g. "G"
            shape:          overall shape of parameter array
            dtype:          numpy dtype
            axis_labels:    axis names
            grids:          dict of grid values, e.g. grid['time'], grid['freq']
            empty:          empty value for undefined parameters, usually 0
            metadata:       optional parameter metadata
        """
        assert(self.mode is "create")
        assert(len(shape) == len(axis_labels))
        # axis index: dict from axis name to axis number
        axis_index = {label: i for i, label in enumerate(axis_labels)}
        assert(all([axis in axis_index for axis in grids.iterkeys()]))
        print>>log(1), "defining parameter '{}' with {} = {}".format(name,
                            ",".join(axis_labels), ",".join(map(str,shape)))
        parmdesc = dict(entry="parmdesc", name=name, shape=shape, dtype=dtype,
                        grids=grids, axis_labels=axis_labels,
                        axis_index=axis_index, empty=empty, metadata=metadata)
        self._parmdescs[name] = parmdesc
        cPickle.dump(parmdesc, self._fobj, 2)

    def add_slice(self, name, array, slices):
        """
        Adds a slice of values for a parameter
        
        Args:
            name:       parameter name e.g. "G"
            array:      array
            slices:     dict of slices into each axis, e.g. {'time':slice(0,100)} defines
                        an array corresponding to the first 100 timeslots
        """
        assert(self.mode is "create")
        parmdesc = self._parmdescs.get(name)
        assert(parmdesc is not None)
        assert(all([axis in parmdesc['axis_index'] for axis in slices]))
        # check that array size matches parmdesc shape, apart from the sliced axes, which can be a subset
        for i, axis in enumerate(parmdesc['axis_labels']):
            if axis not in slices and array.shape[i] != parmdesc['shape'][i]:
                raise ValueError,"axis {[i]}({}) does not match pre-defined shape".format(i,axis)
        # dump to DB
        item = dict(entry="slice", name=name, array=array, slices=slices)
        cPickle.dump(item, self._fobj, 2)

    def close(self):
        """
        Closes the database
        """
        self._fobj.close()
        self._fobj = None
        self.mode = "closed"

    def reload(self):
        """
        Closes and reloads the database
        """
        self.close()
        self.load(self.filename)

    def _load(self, filename):
        """
        Loads database from file. This will create arrays corresponding to the stored parameter shapes.
        """
        self.mode = "load"
        self.filename = filename
        self._parmdescs = {}
        self._arrays = {}
        with open(filename) as fobj:
            while True:
                try:
                    item = cPickle.load(fobj)
                except EOFError:
                    break
                itemtype = item['entry']
                name = item['name']
                if itemtype == "parmdesc":
                    self._parmdescs[name] = item
                    self._arrays[name] = np.full(item['shape'], item['empty'], item['dtype'])
                    print>>log(0),"loading '{}' of shape {}".format(name, ','.join(map(str,item['shape'])))
                elif itemtype == "slice":
                    array = self._arrays.get(name)
                    desc = self._parmdescs.get(name)
                    if name is None or desc is None:
                        raise IOError, "{}: no parmdesc found for {}'".format(filename, name)
                    # form up slice operator to "paste" slice into array
                    total_slice = [slice(None)]*len(desc['shape'])
                    for axis, axis_slice in item['slices'].iteritems():
                        total_slice[desc['axis_index'][axis]] = axis_slice
                    array[total_slice] = item['array']
                else:
                    raise IOError("{}: unknown item type '{}'".format(filename, itemtype))

    def names(self):
        """
        Returns names of all defined parameters
        """
        return self._parmdescs.keys()

    def get(self, name):
        """
        Returns array associated with the named parameter
        """
        assert(self.mode == "load")
        return self._arrays[name]

    def get_desc(self, name):
        """
        Returns description associated with the named parameter
        """
        return self._parmdescs[name]


if __name__ == "__main__":
    print "Creating test DB"
    db = SimpleParameterDB.create("test.db")
    db.define_param("G", (3,10,1,2), np.int32,
                    ["ant", "time", "freq", "corr"],
                    grids={})
    db.define_param("B", (3,1,10,2), np.int32,
                    ["ant", "time", "freq", "corr"],
                    grids={})
    for i0,i1 in (0,2),(4,6),(7,9):
        arr = np.full((3,i1-i0,1,2), i0, np.int32)
        db.add_slice("G", arr, dict(time=slice(i0, i1)))
        arr = np.full((3,1,i1-i0,2), i0, np.int32)
        db.add_slice("B", arr, dict(freq=slice(i0, i1)))
    db.close()

    print "Loading test DB"
    db = SimpleParameterDB.load("test.db")
    print db.names()
    print "G", db.get("G"), db.get_desc("G")
    print "B", db.get("B"), db.get_desc("B")
